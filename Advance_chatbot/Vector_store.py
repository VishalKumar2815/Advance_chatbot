import chromadb
import uuid
import os
from Doc_loader import DOC_LOADER
from Embeddings import Embedder


class VectorDB:
    def __init__(self):
        self.collection_name="My_RAG_DATABASE"                          #store collection with this name
        self.persist_directory=fr"{os.getcwd()}\RAGDB"       # to create vectordb client in this path.
        self.client=None
        self.collection=None
        self._initialize_store()

    def _initialize_store(self):
        try:
            os.makedirs(self.persist_directory,exist_ok=True)
            self.client=chromadb.PersistentClient(self.persist_directory)

            self.collection=self.client.get_or_create_collection(self.collection_name,metadata={"Description":"Document embeddingsfor RAG","hnsw:space":"cosine"})
            if self.collection:
                print("Vector Store Created.✅")
        except Exception as E:
            raise ValueError(E)
    

    def store_data(self,docs,embeds):
        if embeds is None:
            raise ValueError("Embeddings not generated")
        
        if len(docs)!=len(embeds):
            raise ValueError("Embeddings length doesn't meet to Document's lenght.")
        

        id=[]
        metadata=[]
        documents_list=[]
        embeddings_list=[]

        for idx,(docs,embeddings) in enumerate(zip(docs,embeds)):
            doc_id=f"{uuid.uuid4().hex[:8]}_{1}"
            id.append(doc_id)

            meta=dict(docs.metadata)
            meta["dict_index"]=idx
            meta["content_length"]=len(docs.page_content)
            if "Source" in meta:
                meta["Source"] = str(meta["Source"])
            metadata.append(meta)

            documents_list.append(docs.page_content)
            embeddings_list.append(embeddings.tolist())
        
        try:
            self.collection.add(ids=id,embeddings=embeddings_list,metadatas=metadata,documents=documents_list)
            print("Succesfully added document to vector store✅")

        except Exception as e:
            print("Failed to add data to Vector Store.❌")
            print(e)


    

# document_loader=DOC_LOADER()
# embedder=Embedder()
# vectordb=VectorDB()
# chunks=document_loader.load_documents(r"C:\Users\HP\OneDrive\Desktop\10-Practice-SQL-Final-Query-Questions.pdf")
# embeddings=embedder.Embed_docs(chunks)
# vectordb.store_data(chunks,embeddings)



