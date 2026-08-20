import os
import re

from flask import Flask,render_template,redirect,url_for,request,flash,session
from Doc_loader import DOC_LOADER
from Embeddings import Embedder
from Vector_store import VectorDB
from Agent import agent
import datetime
from flask_sqlalchemy import SQLAlchemy
from Forms.form import RegistrationForm,LoginForm
from werkzeug.security import  generate_password_hash,check_password_hash
import uuid
from mcp_doc_server.tools.download_file import register_download_route
from mcp_doc_server.utils import storage
from markupsafe import Markup, escape



app=Flask(__name__)
upload_folder=os.path.join(os.getcwd(), "uploads")


# Exposes GET /download/<token>, serving DB-stored blobs (storage.py) —
# no folder to scan, no path to keep in sync.
register_download_route(app)

# Matches the download URL a conversion tool embeds in its result text.
DOWNLOAD_URL_RE = re.compile(r"/download/[0-9a-f]{32}")


base_dir=os.path.abspath(os.path.dirname(__file__))
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + os.path.join(base_dir, "Userinfo.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SECRET_KEY"] = "super-secret-key"
app.config["UPLOAD_FOLDER"] = "uploads"
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)


db=SQLAlchemy(app)

class User(db.Model):
    id=db.Column(db.Integer,primary_key=True)
    Name=db.Column(db.String(100))
    Email=db.Column(db.String(100))
    Password=db.Column(db.String(100))
    join=db.Column(db.DateTime)

with app.app_context():
    db.create_all()



@app.route("/",methods=["POST","GET"])
def landing_page():
    return render_template("landing.html")


@app.route("/signup",methods=["GET","POST"])
def signup_page():
    form=RegistrationForm()
    if form.validate_on_submit():
        name=form.name.data
        email=form.email.data
        password=generate_password_hash(form.password.data)

        if User.query.filter_by(Email=email).first():
            flash("Email already exist")
            return redirect(url_for("signup_page"))

        user=User(Name=name,Email=email,Password=password,join=datetime.datetime.now())
        db.session.add(user)
        db.session.commit()

        flash(f"Thanks,{name}! You have registered successfully")
        return redirect(url_for("login_page"))

    return render_template("signup.html",form=form)



@app.route("/login",methods=["POST","GET"])
def login_page():
    form=LoginForm()
    if form.validate_on_submit():
        email=form.Email.data
        password=form.Password.data

        user= User.query.filter_by(Email=email).first()
        if user and check_password_hash(user.Password,password):
            flash(f"Welcome,{user.Name}")
            session["id"] = user.id
            session["user_name"] = user.Name
            return redirect(url_for("Chatbot"))
        else:
            flash("Invalid email or password")
            return redirect(url_for("signup_page"))

    return render_template("login.html",form=form)


@app.route("/logout")
def logout():
    session.clear()
    flash("You've been signed out.")
    return redirect(url_for("login_page"))
 

@app.route("/chatbot",methods=["POST","GET"])
def Chatbot():

    doc_loader=DOC_LOADER()
    embedder=Embedder()
    vectordb=VectorDB()
    # persist chat history in session across requests
    if "chats" not in session:
        first_id = str(uuid.uuid4())[:8]
        session["chats"] = {first_id: {"title": "New Chat", "messages": []}}
        session["active_id"] = first_id

    if request.args.get("new"):
        new_id = str(uuid.uuid4())[:8]
        session["chats"][new_id] = {"title": "New Chat", "messages": []}
        session["active_id"]     = new_id
        session.modified = True
        return redirect(url_for("Chatbot"))

     # ── switch chat ───────────────────────────────────────────────────
    switch_id = request.args.get("chat_id")
    if switch_id and switch_id in session["chats"]:
        session["active_id"] = switch_id
        session.modified = True
        return redirect(url_for("Chatbot"))

    # ── delete chat ───────────────────────────────────────────────────
    delete_id = request.args.get("delete")
    if delete_id and delete_id in session["chats"]:
        del session["chats"][delete_id]
        if session["active_id"] == delete_id:
            if session["chats"]:
                session["active_id"] = list(session["chats"].keys())[-1]
            else:
                new_id = str(uuid.uuid4())[:8]
                session["chats"][new_id] = {"title": "New Chat", "messages": []}
                session["active_id"] = new_id
        session.modified = True
        return redirect(url_for("Chatbot"))

    active_id   = session["active_id"]
    active_chat = session["chats"][active_id]


    if request.method=="POST":  
        user=request.form.get("question")
        file=request.files.get("file")
        
        if user.lower() in ["tata","bye","quit","exit"]:
            session.clear()
            return redirect(url_for("landing_page"))
            

        if file and file.filename:
            try:
                os.makedirs(upload_folder, exist_ok=True)
                file_path = os.path.join(upload_folder, file.filename)
                file.save(file_path)

                
                session["last_file"]=file_path
                session.modified = True

                chunks=doc_loader.load_documents(fr"{file_path}")
                embeddings=embedder.Embed_docs(chunks)
                vectordb.store_data(chunks,embeddings)

                
                overview_request= (f"A document was just uploaded. Here is its full text:\n\n"
                                        f"{doc_loader.documents[:6000]}\n\n"
                                        f"Give a brief overview of this document." )

                response=agent.invoke({"messages":[{"role":"user","content":overview_request}]})
                final_answer=response["messages"][-1].content
                print("AI: ",final_answer)

                active_chat["messages"].append({"role": "user",      "content": f"📎 Uploaded: {file.filename}"})
                active_chat["messages"].append({"role": "assistant",  "content": final_answer})
                if active_chat["title"] == "New Chat":
                    active_chat["title"] = f"📎 {file.filename}"
                session.modified = True
            
            except Exception as E:
                active_chat["messages"].append({"role": "assistant", "content": f"Error: {E}"})
                session.modified = True

        elif user:
            if user.startswith("http://") or user.startswith("https://"):
                try:
                    #if not the webbase loader replace with seperate URL tool pipeline.
                    chunks = doc_loader.load_documents(user)  # pass URL directly
                    embeddings = embedder.Embed_docs(chunks)
                    vectordb.store_data(chunks, embeddings)

                    data = doc_loader.documents
                    overview_request = (
                        f"A URL was just loaded: {user}\n\n"
                        f"Here is its content:\n\n{str(data)[:6000]}\n\n"
                        f"Give a brief overview of this page."
                    )
                    response     = agent.invoke({"messages": [{"role": "user", "content": overview_request}]})
                    final_answer = response["messages"][-1].content

                    active_chat["messages"].append({"role": "user",     "content": f"🌐 Loaded: {user}"})
                    active_chat["messages"].append({"role": "assistant", "content": final_answer})
                    if active_chat["title"] == "New Chat": 
                        active_chat["title"] = f"🌐 {user[:40]}"
                    session.modified = True

                except Exception as e:
                    active_chat["messages"].append({"role": "assistant", "content": f"Error loading URL: {e}"})
                    session.modified = True

            else:
                try:
                    history  = active_chat["messages"]
                    overview_request = user
                    if session.get("last_file"):
                        overview_request = (
                            f"{user}\n\n"
                            f"IMPORTANT: If this is a file conversion request, you MUST use this exact "
                            f"file path as input_path (copy it exactly, do not modify or re-derive it): "
                            f"{session['last_file']}"
                        )

                    response=agent.invoke({"messages": history + [{"role": "user", "content": overview_request}]})
                    final_answer=response["messages"][-1].content
                    print("AI: ",final_answer)

                    # A conversion tool embeds "/download/<token>" in its
                    # result text. Scan every message this turn (tool +
                    # final) for it — no folder scanning, no path guessing.
                    download_html = None
                    found_url = None
                    for m in response["messages"]:
                        content = getattr(m, "content", None)
                        if content is None and isinstance(m, dict):
                            content = m.get("content")
                        if content:
                            match = DOWNLOAD_URL_RE.search(str(content))
                            if match:
                                found_url = match.group(0)

                    if found_url:
                        token = found_url.rsplit("/", 1)[-1]
                        record = storage.get_file(token)
                        fname = record["filename"] if record else "download"
                        download_html = str(Markup(
                            f'<br><br>📥 <a class="download-link" href="{found_url}" '
                            f'target="_blank" download>Download {escape(fname)}</a>'
                        ))

                    active_chat["messages"].append({"role": "user", "content": user})
                    active_chat["messages"].append({
                        "role": "assistant",
                        "content": final_answer,        # plain text, auto-escaped normally in template
                        "download_html": download_html, # None if no file, or trusted HTML if there is one
                    })

                    if active_chat["title"] == "New Chat":
                        active_chat["title"] = user[:35] + ("…" if len(user) > 35 else "")
                    session.modified = True
                    
                except Exception as e:
                    active_chat["messages"].append({"role": "assistant", "content": f"Error: {e}"})
                    session.modified = True

            
        
        return redirect(url_for("Chatbot"))
    
    return render_template("Onepage.html", messages=active_chat["messages"],chats=session["chats"],active_id=active_id)
