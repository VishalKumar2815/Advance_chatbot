from pathlib import Path
from langchain_community.document_loaders import CSVLoader,PyPDFLoader,WebBaseLoader,TextLoader,UnstructuredWordDocumentLoader,JSONLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document

import os


class LightweightImageLoader:
    """Minimal LangChain-compatible loader for images — no OCR, no
    unstructured/pi_heif dependency. Returns basic metadata as the
    page_content so the file still flows through the existing
    load -> chunk -> embed pipeline without special-casing it there."""

    def __init__(self, file_path: str):
        self.file_path = file_path

    def load(self):
        from PIL import Image

        p = Path(self.file_path)
        img = Image.open(p)

        content = (
            f"Image file: {p.name}\n"
            f"Format: {img.format}\n"
            f"Dimensions: {img.size[0]}x{img.size[1]}\n"
            f"Mode: {img.mode}\n"
            f"File size: {p.stat().st_size} bytes"
        )

        return [Document(page_content=content, metadata={"source": str(p)})]


class DOC_LOADER:
    def __init__(self):
        self.loader=None
        self.file_type=None
        self.documents=None
        self.doc_path=None

    def check_file_dir(self,doc_path:str):
        if os.path.isdir(doc_path):
            for files in os.listdir(doc_path):
                self.doc_path=os.path.join(doc_path,files)
        else:
            self.doc_path=doc_path
        
    
    def check_file_type(self):
        if self.doc_path.endswith(".csv"):
            self.loader=CSVLoader(self.doc_path)
            self.file_type="CSV File"
        elif self.doc_path.endswith((".pdf","pdfx")):
            self.file_type="PDF File"
            self.loader=PyPDFLoader(self.doc_path)
        elif self.doc_path.endswith(".docx"):
            self.loader=UnstructuredWordDocumentLoader(self.doc_path)
            self.file_type="WORD File"
        elif self.doc_path.endswith(".json"):
            self.file_type="JSON File"
            self.loader=JSONLoader(self.doc_path)
        elif self.doc_path.endswith(".html"):
            self.loader=WebBaseLoader(self.doc_path)
            self.file_type="HTML File"
        elif self.doc_path.endswith(".txt"):
            self.file_type="TEXT File"
            self.loader=TextLoader(self.doc_path)
        elif self.doc_path.endswith((".png",".jpg",".jpeg",".webp")):
            self.file_type="IMAGE File"
            self.loader=LightweightImageLoader(self.doc_path)
        elif self.doc_path.endswith((".py",".js")):
            self.file_type="CODE File"
            self.loader=TextLoader(self.doc_path)
        elif self.doc_path.startswith("http://") or self.doc_path.startswith("https://"):
            self.file_type="URL File"
            self.loader=WebBaseLoader(self.doc_path)
        else:
            return None
        
    
    def Chunker(self,docs):
        splitter=RecursiveCharacterTextSplitter()
        chunks=splitter.split_documents(docs)
        if not chunks:
            raise ValueError("Chunking Failed ❌")
        else:
            print("Chunks generated sucessfully ✅")
        return chunks

        
    def load_documents(self,file:str):
        self.check_file_dir(file)
        self.check_file_type()

        print(self.loader,"\n")
        print(self.file_type,"\n")
        print(self.doc_path,"\n")

        self.documents=self.loader.load()
        if self.documents is not None:
            print("Documents Loaded successfuly  ✅")
            for doc in self.documents:
                document=Path(self.doc_path)
                doc.metadata["Source"]=document
                doc.metadata["File Type"]=self.file_type
            
            chunks=self.Chunker(self.documents)
        else:
            raise ValueError("Failed to initialize documents  ❌")
        return chunks


