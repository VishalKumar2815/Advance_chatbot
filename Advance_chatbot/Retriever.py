from Embeddings import Embedder
from Vector_store import VectorDB
from typing import List,Dict


class DOCRetriever:
    def __init__(self):
        self.vectorstore=VectorDB()
        self.embedding_manager=Embedder()


    def retrieve(self,query:str,top_k:int=5,score_threshold:float=0.50)->List[Dict[str,any]]:
        """
        *we need to embed query and then 
        *search into vectorstore.
        
        """
        embed_query=self.embedding_manager.Embed_query([query])[0]
        try:
            result=self.vectorstore.collection.query(query_embeddings=[embed_query.tolist()],
            n_results=top_k)
            

            retrieved_docs=[]

            if result["documents"] and result["documents"][0]:
                documents=result["documents"][0]
                metadatas=result["metadatas"][0]
                distances=result["distances"][0]
                ids=result["ids"][0]


                for i,(doc_id,document,metadata,distance) in enumerate(zip(ids,documents,metadatas,distances)):

                    similarity_score = 1 / (1 + distance)

                    if similarity_score>=score_threshold:
                        retrieved_docs.append({
                            "ids":doc_id,
                            "content":document,
                            "metadata":metadata,
                            "similarity_score":similarity_score,
                            "rank":i+1}
                        )

                    print("Query embeddings generated successfully✅")
            else:
                print("nothing found in this document!")
                return None
                
            return retrieved_docs

        except Exception as E:
            print ("Could not generate embeddings!❌")
            print(E)
            return []



# retriever=DOCRetriever()
# docs=retriever.retrieve("hired in 2000.")
# print(docs[0]["content"] )



