from fastembed import TextEmbedding
from typing import List
import numpy as np


class Embedder:
    def __init__(self, model_name: str = "BAAI/bge-small-en-v1.5"):
        self.model_name = model_name
        self.model = None
        self._load_model()

    def _load_model(self):
        try:
            self.model = TextEmbedding(model_name=self.model_name)
            print("Embedding model loaded ✅")
        except Exception as E:
            print(E)

    def embed_text(self, text: List[str]) -> np.ndarray:
        try:
            embeddings = list(self.model.embed(text))   # generator ko consume + list bana rahe hain
            embeddings = np.array(embeddings)             # numpy array mein convert, downstream compatibility ke liye
            print("Successfuly generated embeddings✅✅✅")
            return embeddings
        except Exception as E:
            print("Failed to load embeddings!❌")
            print(E)
