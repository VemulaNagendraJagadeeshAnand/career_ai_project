import os
import io
import docx
import certifi
from datetime import datetime
from flask import Flask, render_template, request, redirect, session, url_for
from pymongo import MongoClient
from werkzeug.security import generate_password_hash, check_password_hash

# NLP & Extraction Libraries
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from pdfminer.high_level import extract_text

app = Flask(__name__)
app.secret_key = "career_ai_jntuk_2026_full_v7"

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

# ---------------- KNOWLEDGE BASE & ROADMAPS ----------------
CAREERS = {
    "Data Scientist": ["python", "machine learning", "statistics", "sql", "pandas", "data visualization"],
    "Web Developer": ["html", "css", "javascript", "react", "node", "express", "mongodb"],
    "AI Engineer": ["python", "deep learning", "neural networks", "tensorflow", "pytorch", "nlp"],
    "Business Analyst": ["excel", "sql", "power bi", "tableau", "communication", "agile"],
    "Cybersecurity Analyst": ["networking", "firewalls", "penetration testing", "wireshark", "linux"],
    "Cloud Engineer": ["aws", "azure", "docker", "kubernetes", "terraform", "cloud computing"],
    "Java Developer": ["java", "spring boot", "hibernate", "maven", "microservices", "mysql"]
}

ROADMAPS = {
    "python": "https://www.youtube.com/results?search_query=python+tutorial",
    "machine learning": "https://www.coursera.org/learn/machine-learning",
    "sql": "https://www.khanacademy.org/computing/computer-programming/sql",
    "react": "https://react.dev/learn",
    "aws": "https://aws.amazon.com/training/digital/",
    "docker": "https://www.docker.com/101-tutorial/",
    "java": "https://dev.java/learn/"
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

def get_ai_scores(text, target_profiles):
    """Refined NLP Engine using TF-IDF and N-Grams"""
    text = text.lower()
    names = list(target_profiles.keys())
    profiles = [" ".join(v) if isinstance(v, list) else v for v in target_profiles.values()]
    
    corpus = [text] + profiles
    vec = TfidfVectorizer(stop_words='english', ngram_range=(1, 2)) 
    matrix = vec.fit_transform(corpus)
    similarity = cosine_similarity(matrix[0:1], matrix[1:])[0]
    
    results = {}
    for i, name in enumerate(names):
        skills_list = target_profiles[name]
        matched = [w for w in skills_list if w.lower() in text]
        missing = [w for w in skills_list if w.lower() not in text]
        
        results[name] = {
            "score": round(float(similarity[i]) * 100, 2),
            "matches": matched,
            "missing": missing,
            "roadmap": {m: ROADMAPS.get(m.lower(), "#") for m in missing}
        }
    return dict(sorted(results.items(), key=lambda x: x[1]['score'], reverse=True))

# ---------------- ROUTES ----------------

@app.route("/")
def welcome(): 
    return render_template("welcome.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        u = request.form.get("username")
        p = request.form.get("password")
        hashed_pw = generate_password_hash(p)
        
        if not students_col.find_one({"username": u}):
            students_col.insert_one({
                "username": u, "email": request.form.get("email"), 
                "password": hashed_pw, "role": request.form.get("role", "student"), "history": []
            })
            return redirect(url_for("login"))
    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        role_selected = request.form.get("role") 
        u = request.form.get("username") 
        p = request.form.get("password") 
        user = students_col.find_one({"username": u, "role": role_selected})
        
        if user and check_password_hash(user['password'], p):
            session[role_selected] = u
            if role_selected == "admin":
                return redirect(url_for("admin"))
            else:
                return redirect(url_for("student_dashboard"))
        else:
            return render_template("login.html", error="Invalid Credentials or Role Selection")
    return render_template("login.html")

@app.route("/dashboard")
def student_dashboard():
    if "student" not in session: 
        return redirect(url_for("login"))
    
    user_data = students_col.find_one({"username": session["student"]})
    history = user_data.get("history", [])
    
    recommendation = None
    level = "Novice"
    if history:
        latest = history[-1]
        score = latest.get("ats", 0)
        
        if score > 80: level = "Platinum (Job-Ready)"
        elif score > 60: level = "Gold"
        elif score > 30: level = "Silver"
        
        missing = latest.get("missing", [])
        if missing:
            recommendation = {"skill": missing[0], "link": ROADMAPS.get(missing[0].lower(), "#")}

    return render_template("student_dashboard.html", user=user_data, history=history, recommendation=recommendation, level=level)

@app.route("/resume_screening", methods=["GET", "POST"])
def resume_screening():
    if "student" not in session: return redirect(url_for("login"))
    result = None
    if request.method == "POST":
        file = request.files.get("resume")
        text = extract_text_from_file(file)
        if text:
            scores_data = get_ai_scores(text, CAREERS)
            career_match, data = list(scores_data.items())[0]
            
            result = {
                "career": career_match, "ats_score": data['score'],
                "matches": data['matches'], "missing": data['missing'],
                "roadmap": data['roadmap']
            }
            
            students_col.update_one({"username": session["student"]}, {"$push": {"history": {
                "career": career_match, "ats": data['score'], "missing": data['missing'], 
                "timestamp": datetime.now().strftime("%Y-%m-%d")
            }}}) 
    return render_template("resume_screening.html", result=result)

@app.route("/career_guidance", methods=["GET", "POST"])
def career_guidance():
    if "student" not in session: return redirect(url_for("login"))
    result = None
    if request.method == "POST":
        skills = request.form.get("skills", "")
        if skills:
            result = get_ai_scores(skills, CAREERS)
    return render_template("career_guidance.html", result=result)

@app.route("/custom_match", methods=["GET", "POST"])
def custom_match():
    if "student" not in session: return redirect(url_for("login"))
    result = None
    if request.method == "POST":
        jd_text = request.form.get("jd_text")
        file = request.files.get("resume")
        resume_text = extract_text_from_file(file)
        if resume_text and jd_text:
            custom_profile = {"Custom Target": jd_text}
            scores = get_ai_scores(resume_text, custom_profile)
            result = list(scores.values())[0]
    return render_template("custom_match.html", result=result)

@app.route("/admin_bulk_screen", methods=["GET", "POST"])
def admin_bulk_screen():
    if "admin" not in session: return redirect(url_for("login"))
    results = []
    if request.method == "POST":
        files = request.files.getlist("resumes")
        for file in files:
            text = extract_text_from_file(file)
            if text:
                scores_data = get_ai_scores(text, CAREERS)
                career_match, data = list(scores_data.items())[0]
                results.append({"filename": file.filename, "career": career_match, "ats_score": data['score']})
        results = sorted(results, key=lambda x: x['ats_score'], reverse=True)
    return render_template("admin_bulk.html", results=results)

@app.route("/admin")
def admin():
    if "admin" not in session: return redirect(url_for("login"))
    all_users = list(students_col.find())
    career_dist = {c: 0 for c in CAREERS.keys()}
    total_screenings = 0

    for u in all_users:
        hist = u.get('history', [])
        total_screenings += len(hist)
        for e in hist:
            c = e.get('career')
            if c in career_dist: career_dist[c] += 1

    top_career = max(career_dist, key=career_dist.get) if total_screenings > 0 else "No Data"

    return render_template("admin.html", 
        users=all_users, 
        analytics={"users": len(all_users), "resumes": total_screenings}, 
        career_labels=list(career_dist.keys()), 
        career_values=list(career_dist.values()), 
        top_career=top_career)

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("welcome"))

if __name__ == "__main__":
    app.run(debug=True)