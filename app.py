import os
import io
import docx
import certifi
from datetime import datetime
from flask import Flask, render_template, request, redirect, session, url_for
from pymongo import MongoClient

# NLP & Extraction Libraries
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from pdfminer.high_level import extract_text

app = Flask(__name__)
app.secret_key = "career_ai_jntuk_2026_project"

# ---------------- DATABASE CONFIGURATION ----------------
uri = "mongodb+srv://226m1a05a4_db_user:JagadeeshAnand@career.cjjjztp.mongodb.net/?retryWrites=true&w=majority&appName=career"
ca = certifi.where()

try:
    client = MongoClient(uri, tlsCAFile=ca, serverSelectionTimeoutMS=10000)
    db = client["career_ai_database"]
    students_col = db["students"]
    client.admin.command('ping') 
    print("✅ MongoDB Atlas Connected Successfully")
except Exception as e:
    print(f"❌ Database Connection Error: {e}")

# ---------------- KNOWLEDGE BASE ----------------
CAREERS = {
    "Data Scientist": ["python", "machine learning", "statistics", "sql", "pandas", "data visualization"],
    "Web Developer": ["html", "css", "javascript", "react", "node", "express", "mongodb"],
    "AI Engineer": ["python", "deep learning", "neural networks", "tensorflow", "pytorch", "nlp"],
    "Business Analyst": ["excel", "sql", "power bi", "tableau", "communication", "agile"],
    "Cybersecurity Analyst": ["networking", "firewalls", "penetration testing", "wireshark", "linux"],
    "Cloud Engineer": ["aws", "azure", "docker", "kubernetes", "terraform", "cloud computing"],
    "Java Developer": ["java", "spring boot", "hibernate", "maven", "microservices", "mysql"]
}

# ---------------- CORE AI LOGIC ----------------

def extract_text_from_file(file):
    filename = file.filename.lower()
    try:
        file.seek(0)
        file_bytes = file.read()
        file_stream = io.BytesIO(file_bytes)
        if filename.endswith(".pdf"):
            return " ".join(extract_text(file_stream).split())
        elif filename.endswith(".docx"):
            doc = docx.Document(file_stream)
            return " ".join([p.text for p in doc.paragraphs])
    except: return ""
    return ""

def get_ai_scores(text, careers_db):
    text = text.lower()
    career_names = list(careers_db.keys())
    career_profiles = [" ".join(v) for v in careers_db.values()]
    corpus = [text] + career_profiles
    vec = TfidfVectorizer(stop_words='english')
    matrix = vec.fit_transform(corpus)
    similarity = cosine_similarity(matrix[0:1], matrix[1:])[0]
    
    results = {}
    for i, career in enumerate(career_names):
        matched = [word for word in careers_db[career] if word in text]
        missing = [word for word in careers_db[career] if word not in text]
        results[career] = {
            "score": round(float(similarity[i]) * 100, 2),
            "matches": matched,
            "missing": missing
        }
    return dict(sorted(results.items(), key=lambda x: x[1]['score'], reverse=True))

# ---------------- ROUTES ----------------

@app.route("/")
def welcome(): 
    return render_template("welcome.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        role_selected = request.form.get("role") 
        u = request.form.get("username") 
        p = request.form.get("password") 
        user = students_col.find_one({"username": u, "password": p, "role": role_selected})
        
        if user:
            if role_selected == "admin":
                session["admin"] = u
                return redirect(url_for("admin"))
            else:
                session["user"] = u
                return redirect(url_for("student_dashboard"))
        else:
            return render_template("login.html", error="Invalid Credentials or Role Selection")
    return render_template("login.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        u = request.form.get("username")
        e = request.form.get("email")
        p = request.form.get("password")
        i = request.form.get("interest", "Student") 
        role = request.form.get("role", "student") 

        if not students_col.find_one({"username": u}):
            students_col.insert_one({
                "username": u, "email": e, "password": p, 
                "interest": i, "role": role, "history": []
            })
            return redirect(url_for("login"))
    return render_template("register.html")

@app.route("/dashboard")
def student_dashboard():
    if "user" not in session: return redirect(url_for("login"))
    user_data = students_col.find_one({"username": session["user"]})
    return render_template("student_dashboard.html", user=user_data, history=user_data.get("history", []))

@app.route("/resume_screening", methods=["GET", "POST"])
def resume_screening():
    if "user" not in session and "admin" not in session: 
        return redirect(url_for("login"))
    result = None
    if request.method == "POST":
        file = request.files.get("resume")
        if file and file.filename != "":
            text = extract_text_from_file(file)
            if text:
                scores_data = get_ai_scores(text, CAREERS)
                career_match, data = list(scores_data.items())[0]
                ats_score = min(100, (data['score'] * 0.80) + 20)
                
                result = {
                    "career": career_match, 
                    "ats_score": round(ats_score, 2),
                    "matches": data['matches'],
                    "missing": data['missing']
                }
                
                if "user" in session:
                    students_col.update_one(
                        {"username": session["user"]}, 
                        {"$push": {"history": {"career": career_match, "ats": round(ats_score, 2), "timestamp": datetime.now().strftime("%Y-%m-%d")}} }
                    ) 
    return render_template("resume_screening.html", result=result)

@app.route("/career_guidance", methods=["GET", "POST"])
def career_guidance():
    if "user" not in session and "admin" not in session: 
        return redirect(url_for("login"))
    result = None
    if request.method == "POST":
        skills = request.form.get("skills", "")
        if skills:
            result = get_ai_scores(skills, CAREERS)
    return render_template("career_guidance.html", result=result)

@app.route("/admin_bulk_screen", methods=["GET", "POST"])
def admin_bulk_screen():
    if "admin" not in session: return redirect(url_for("login"))
    results = []
    if request.method == "POST":
        files = request.files.getlist("resumes")
        for file in files:
            if file and file.filename != "":
                text = extract_text_from_file(file)
                if text:
                    scores_data = get_ai_scores(text, CAREERS)
                    career_match, data = list(scores_data.items())[0]
                    ats_score = min(100, (data['score'] * 0.80) + 20)
                    results.append({
                        "filename": file.filename, 
                        "career": career_match, 
                        "ats_score": round(ats_score, 2)
                    })
        results = sorted(results, key=lambda x: x['ats_score'], reverse=True)
    return render_template("admin_bulk.html", results=results)

@app.route("/admin")
def admin():
    if "admin" not in session: return redirect(url_for("login"))
    all_users = list(students_col.find())
    
    # CALCULATE DISTRIBUTION
    career_dist = {c: 0 for c in CAREERS.keys()}
    total_screenings = 0
    for u in all_users:
        hist = u.get('history', [])
        total_screenings += len(hist)
        for e in hist:
            career_name = e.get('career')
            if career_name in career_dist: 
                career_dist[career_name] += 1
    
    top_career = max(career_dist, key=career_dist.get) if total_screenings > 0 else "No Data"
    
    return render_template("admin.html", 
        users=all_users, 
        analytics={"users": len(all_users), "resumes": total_screenings}, 
        career_labels=list(career_dist.keys()), 
        career_values=list(career_dist.values()), 
        top_career=top_career)

@app.route("/fix_database_roles")
def fix_database_roles():
    result = students_col.update_many({"role": {"$exists": False}}, {"$set": {"role": "student"}})
    return f"Updated {result.modified_count} users to 'student' role!"

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("welcome"))

if __name__ == "__main__":
    app.run(debug=True)