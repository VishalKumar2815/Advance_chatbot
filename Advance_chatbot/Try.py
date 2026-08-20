from flask import Flask,render_template,redirect,url_for,request
from Doc_loader import DOC_LOADER
from Embeddings import Embedder
from Vector_store import VectorDB
from Agent import agent



# app=Flask(__name__)


def Chatbot():
    doc_loader=DOC_LOADER()
    embedder=Embedder()
    vectordb=VectorDB()
    history=[]


    while True:
        user=input("User: ").strip('""')
        if user.lower() in ["tata","bye","stop","quit","exit"]:
            break
            
        if user.endswith((".py",".pdf",".docx",".txt",".html",".json",".csv")):
            try:

                chunks=doc_loader.load_documents(fr"{user}")
                embeddings=embedder.Embed_docs(chunks)
                vectordb.store_data(chunks,embeddings)


                data=[doc.page_content for doc in doc_loader.documents]
                overview_request= (f"A document was just uploaded. Here is its full text:\n\n"
                                        f"{data[:6000]}\n\n"
                                        f"Give a brief overview of this document." )
                history.append({"role": "user", "content": overview_request}) 
                print(history) 

                response=agent.invoke({"messages":history})
                final_answer=response["messages"][-1].content
                print("AI: ",final_answer)  
            
            except Exception as E:
                raise ValueError(E)
        
        history.append({"role": "user", "content": user})
        try:
            response=agent.invoke({"messages":history})
            final_answer=response["messages"][-1].content
            print("AI: ",final_answer)  
        except Exception as E:
            raise ValueError(E)


Chatbot()



                


