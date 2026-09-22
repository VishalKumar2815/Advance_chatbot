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
                embeddings=embedder.embed_chunks(chunks)
                vectordb.store_data(chunks,embeddings) 

                data="".join(doc.page_content for doc in doc_loader.documents)  # was list-slice bug
                overview_request= (f"A document was just uploaded. Here is its full text:\n\n"
                                        f"{data[:6000]}\n\n"
                                        f"Give a brief overview of this document." )

                response=agent.invoke({"messages": history + [{"role": "user", "content": overview_request}]})
                final_answer=response["messages"][-1].content
                print("AI: ",final_answer)

                # keep history light — don't permanently store the full document dump
                history.append({"role": "user", "content": f"[uploaded document: {user}]"})
                history.append({"role": "assistant", "content": final_answer})

            except Exception as E:
                print(f"Error: {E}")

            continue   # was missing — file path was falling through and being sent as a second question

        history.append({"role": "user", "content": user})
        try:
            response=agent.invoke({"messages":history})
            final_answer=response["messages"][-1].content
            print("AI: ",final_answer)
            history.append({"role": "assistant", "content": final_answer})
        except Exception as E:
            print(f"Error: {E}")


Chatbot()