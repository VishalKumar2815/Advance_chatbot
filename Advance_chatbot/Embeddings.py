from sentence_transformers import SentenceTransformer
from Doc_loader import DOC_LOADER
from typing import List
import numpy as np



class Embedder:
    def __init__(self,model_name:str="all-MiniLM-L6-v2"):
        self.model=None
        self.model_name=model_name
        self.embeddings=None
        self._intitalise_model()

    
    def _intitalise_model(self):
        self.model=SentenceTransformer(self.model_name)
        if self.model:
            print("Embedding model loaded ✅")
        else:
            print("Failed to load Embedding model ❌")
    

    def Embed_docs(self,chunks:List[str])->np.ndarray:
        docs=[doc.page_content for doc in chunks]
        try:
            self.embeddings=self.model.encode(docs,show_progress_bar=True)
            if self.embeddings is not None:
                print("embeddings generated successfuly ✅")
            return self.embeddings
        except Exception as e:
            print(e)
    
    def Embed_query(self,chunks:List[str])->np.ndarray:
        try:
            self.embeddings=self.model.encode(chunks,show_progress_bar=True)
            return self.embeddings
        except Exception as e:
            print(e)



# loader=DOC_LOADER()
# embedder=Embedder()
# chunks=loader.load_documents(r"C:\Users\HP\OneDrive\Desktop\10-Practice-SQL-Final-Query-Questions.pdf")
# embeded_text=embedder.Embed_docs(chunks)

# print(embeded_text)

