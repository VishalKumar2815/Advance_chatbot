"""
YouTube ingestion — single video OR full playlist.

Produces the same langchain_core.documents.Document chunks that
Doc_loader.py produces (page_content + metadata dict), so it plugs into
the same downstream flow:

    chunks = YoutubeLoader(url=url).load()
    embeddings = embedder.embed_text([c.page_content for c in chunks])
    vectordb.store_data(chunks, embeddings)

Error handling:
  - One bad video never kills the playlist; it is skipped WITH a reason.
  - Permanent failures (captions disabled, private video, IP blocked) are
    NOT retried. Only unexpected/transient errors get retry + backoff.
  - If YouTube starts blocking requests, the loop stops instead of
    hammering it, and the final error says so.
  - A small delay between videos keeps playlists from tripping rate limits.
  - load() only raises if the URL is bad or EVERY video failed, and the
    error message then contains the per-video reasons.

Requires:  pip install yt-dlp youtube-transcript-api
"""

import time
from typing import List, Optional, Tuple

from langchain_core.documents import Document
from youtube_transcript_api import (
    YouTubeTranscriptApi,
    TranscriptsDisabled,
    NoTranscriptFound,
    VideoUnavailable,
)
from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError

# These exist only in newer youtube-transcript-api versions; define
# harmless stand-ins so this file works on any version.
try:
    from youtube_transcript_api import RequestBlocked, IpBlocked
except ImportError:
    class RequestBlocked(Exception): pass
    class IpBlocked(Exception): pass

try:
    from youtube_transcript_api import NotTranslatable, TranslationLanguageNotAvailable
except ImportError:
    class NotTranslatable(Exception): pass
    class TranslationLanguageNotAvailable(Exception): pass


class _NoTranscriptAvailable(Exception):
    """Video has no captions of any kind."""


_BLOCKED = (RequestBlocked, IpBlocked)
_PERMANENT = (TranscriptsDisabled, NoTranscriptFound, VideoUnavailable,
              _NoTranscriptAvailable) + _BLOCKED


# ---------------------------------------------------------------- retry
def _retry(max_attempts: int = 3, base_delay: float = 2.0):
    """Retries only unexpected/transient errors. Permanent errors are
    re-raised immediately (retrying can't fix them), and after the last
    attempt the real exception is re-raised too, so the caller can report
    the actual reason instead of a silent None."""
    def decorator(fn):
        def wrapper(*args, **kwargs):
            last_err = None
            for attempt in range(1, max_attempts + 1):
                try:
                    return fn(*args, **kwargs)
                except _PERMANENT:
                    raise
                except Exception as e:
                    last_err = e
                    if attempt < max_attempts:
                        delay = base_delay * (2 ** (attempt - 1))
                        print(f"  retry {attempt}/{max_attempts} in {delay:.0f}s: {e}")
                        time.sleep(delay)
            raise last_err
        return wrapper
    return decorator


class YoutubeLoader:
    def __init__(self, url: Optional[str] = None, target_lang: str = "en",
                 chunk_seconds: int = 45, request_delay: float = 1.0):
        """url is optional so this works standalone (YoutubeLoader().load(url))
        and from Doc_loader.py (YoutubeLoader(url=path).load()).
        request_delay = seconds to wait between videos in a playlist."""
        self.url = url
        self.target_lang = target_lang
        self.chunk_seconds = chunk_seconds
        self.request_delay = request_delay
        self.file_type = "YOUTUBE VIDEO"
        self._blocked = False

    # ------------------------------------------------------ URL -> videos
    def _extract_videos(self, url: str) -> List[dict]:
        opts = {"quiet": True, "extract_flat": True, "skip_download": True}
        try:
            with YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=False)
        except DownloadError as e:
            raise ValueError(f"Could not read this YouTube URL (private, deleted, or invalid?): {e}")
        except Exception as e:
            raise ValueError(f"Unexpected error reading YouTube URL: {e}")

        if info is None:
            raise ValueError("YouTube returned no data for this URL.")

        if "entries" in info:  # playlist
            entries = [e for e in info["entries"] if e and e.get("id")]
            if not entries:
                raise ValueError("This playlist is empty or all videos are unavailable.")
            videos = [{"id": e["id"], "title": e.get("title") or e["id"]} for e in entries]
        else:  # single video
            if not info.get("id"):
                raise ValueError("Could not extract a video ID from this URL.")
            videos = [{"id": info["id"], "title": info.get("title") or info["id"]}]

        seen, unique = set(), []
        for v in videos:
            if v["id"] not in seen:
                seen.add(v["id"])
                unique.append(v)
        return unique

    # ------------------------------------------------------ transcript fetch
    @staticmethod
    def _list_transcripts(video_id: str):
        """API changed in youtube-transcript-api v1.0:
           <1.0 : YouTubeTranscriptApi.list_transcripts(video_id)
           >=1.0: YouTubeTranscriptApi().list(video_id)"""
        if hasattr(YouTubeTranscriptApi, "list_transcripts"):
            return YouTubeTranscriptApi.list_transcripts(video_id)
        return YouTubeTranscriptApi().list(video_id)

    @_retry(max_attempts=3, base_delay=2.0)
    def _fetch_raw_transcript(self, video_id: str):
        transcript_list = self._list_transcripts(video_id)
        available = list(transcript_list)   # manual captions come first, then auto-generated
        if not available:
            raise _NoTranscriptAvailable("no captions exist for this video")

        try:
            transcript = transcript_list.find_transcript([self.target_lang])
        except NoTranscriptFound:
            transcript = available[0]
            try:
                transcript = transcript.translate(self.target_lang)
            except (NotTranslatable, TranslationLanguageNotAvailable):
                # better to keep the original-language text than lose the video
                print(f"  ⚠️ can't translate to '{self.target_lang}', "
                      f"keeping original language ({transcript.language_code})")

        fetched = transcript.fetch()
        # v1.0+ returns a FetchedTranscript object; normalize to list of dicts
        if hasattr(fetched, "to_raw_data"):
            return fetched.to_raw_data()
        return fetched

    def _get_transcript(self, video_id: str) -> Tuple[Optional[list], Optional[str]]:
        """Returns (segments, None) on success, or (None, reason) on failure —
        so the caller can report WHY a video failed."""
        try:
            return self._fetch_raw_transcript(video_id), None
        except _BLOCKED:
            self._blocked = True
            return None, "YouTube is blocking requests from this IP (rate limit) — try again later"
        except TranscriptsDisabled:
            return None, "captions are disabled for this video"
        except (NoTranscriptFound, _NoTranscriptAvailable):
            return None, "no captions available in any language"
        except VideoUnavailable:
            return None, "video unavailable (private, deleted or region-locked)"
        except Exception as e:
            return None, f"{type(e).__name__}: {e}"

    # ------------------------------------------------------ chunking
    def _chunk_transcript(self, segments, video_id: str, title: str) -> List[Document]:
        if not segments:
            return []

        chunks = []
        buf_text, buf_start, buf_end = [], None, None

        for seg in segments:
            if buf_start is None:
                buf_start = seg["start"]
            buf_text.append(seg["text"])
            buf_end = seg["start"] + seg.get("duration", 0)

            if buf_end - buf_start >= self.chunk_seconds:
                chunks.append(self._make_doc(buf_text, buf_start, buf_end, video_id, title))
                buf_text, buf_start, buf_end = [], None, None

        if buf_text:
            chunks.append(self._make_doc(buf_text, buf_start, buf_end, video_id, title))

        return chunks

    def _make_doc(self, text_parts, start, end, video_id, title) -> Document:
        content = " ".join(text_parts).strip()
        timestamped_url = f"https://youtube.com/watch?v={video_id}&t={int(start)}s"
        return Document(
            page_content=content,
            metadata={
                "Source": timestamped_url,
                "File Type": self.file_type,
                "video_id": video_id,
                "video_title": title,
                "start_time": round(start, 1),
                "end_time": round(end, 1),
            },
        )

    # ------------------------------------------------------ public API
    def load(self, url: Optional[str] = None) -> List[Document]:
        url = url or self.url
        if not url:
            raise ValueError("No YouTube URL provided (pass one to load(), or to the constructor).")

        self._blocked = False
        videos = self._extract_videos(url)
        print(f"Found {len(videos)} video(s) in this URL\n")

        all_chunks: List[Document] = []
        succeeded: List[str] = []
        failed: List[Tuple[str, str]] = []      # (title, reason)

        for i, v in enumerate(videos):
            if self._blocked:
                remaining = len(videos) - i
                print(f"\n⛔ YouTube is blocking requests — stopping. {remaining} video(s) not attempted.")
                for rest in videos[i:]:
                    failed.append((rest["title"], "not attempted (requests blocked)"))
                break

            print(f"[{i + 1}/{len(videos)}] '{v['title']}' ({v['id']})")
            try:
                segments, reason = self._get_transcript(v["id"])
                if not segments:
                    print(f"  ❌ {reason}")
                    failed.append((v["title"], reason))
                else:
                    video_chunks = self._chunk_transcript(segments, v["id"], v["title"])
                    if not video_chunks:
                        print("  ❌ transcript was empty")
                        failed.append((v["title"], "transcript was empty"))
                    else:
                        all_chunks.extend(video_chunks)
                        succeeded.append(v["title"])
                        print(f"  ✅ {len(video_chunks)} chunks")
            except Exception as e:
                print(f"  ❌ unexpected error: {type(e).__name__}: {e}")
                failed.append((v["title"], f"{type(e).__name__}: {e}"))

            if i < len(videos) - 1 and self.request_delay:
                time.sleep(self.request_delay)

        print(f"\nDone: {len(succeeded)} succeeded, {len(failed)} failed (of {len(videos)})")
        for title, reason in failed:
            print(f"  - {title}: {reason}")

        if not all_chunks:
            shown = "; ".join(f"{t}: {r}" for t, r in failed[:3])
            more = f" (+{len(failed) - 3} more)" if len(failed) > 3 else ""
            raise ValueError(
                f"No transcript could be extracted from any of the {len(videos)} video(s) ❌ "
                f"Reasons — {shown}{more}"
            )

        return all_chunks


# chunks = YoutubeLoader().load("https://www.youtube.com/playlist?list=XXXXXXXXXXX")
# print(chunks[0].page_content, chunks[0].metadata)