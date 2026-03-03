import io
import os
import docx
from datetime import datetime
from flask import Flask, render_template, request, redirect, session, url_for
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from pdfminer.high_level import extract_text
from pymongo import MongoClient
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "career_ai_jntuk_project")

# ---------------- MONGODB ATLAS CLOUD CONFIGURATION ----------------
# Use environment variable for the URI to fix the security vulnerability
uri = os.getenv("MONGO_URI")

try:
    # Adding TLS configurations often required for cloud deployment
    client = MongoClient(uri, serverSelectionTimeoutMS=30000)
    db = client["career_ai_database"]
    students_col = db["students"]
    client.admin.command('ping')
    print("Successfully connected to MongoDB Atlas Cloud!")
except Exception as e:
    print(f"MongoDB Atlas Connection Error: {e}")

# ---------------- CAREER KNOWLEDGE BASE ----------------
CAREERS = {
    "Data Scientist": ["python", "machine learning", "statistics", "sql", "pandas", "data visualization", "scikit-learn"],
    "Web Developer": ["html", "css", "javascript", "react", "node", "express", "mongodb", "angular", "bootstrap"],
    "AI Engineer": ["python", "deep learning", "neural networks", "tensorflow", "pytorch", "nlp", "computer vision"],
    "Business Analyst": ["excel", "sql", "power bi", "tableau", "communication", "agile", "scrum", "analytics"],
    "Cybersecurity Analyst": ["networking", "firewalls", "penetration testing", "wireshark", "linux", "siem", "encryption", "ethical hacking", "owasp"],
    "Cloud Engineer": ["aws", "azure", "docker", "kubernetes", "terraform", "cloud computing", "devops", "linux", "serverless"],
    "Java Developer": ["java", "spring boot", "hibernate", "maven", "microservices", "mysql", "multithreading", "oops"]
}

CAREER_ROADMAP = {
    "Data Scientist": {
        "skills": ["Python", "Statistics", "Machine Learning"], 
        "tools": ["Pandas", "SQL"], "time": "6–12 months",
        "resources": [{"name": "NPTEL Data Science", "url": "https://nptel.ac.in/courses/106106179"}]
    },
    "Web Developer": {
        "skills": ["HTML", "CSS", "JavaScript"], 
        "tools": ["React", "Node.js"], "time": "4–8 months",
        "resources": [{"name": "FreeCodeCamp Web Cert", "url": "https://www.freecodecamp.org/"}]
    },
    "Cybersecurity Analyst": {
        "skills": ["Networking", "Ethical Hacking"], 
        "tools": ["Kali Linux", "Wireshark"], "time": "6–10 months",
        "resources": [{"name": "TryHackMe Path", "url": "https://tryhackme.com/"}]
    },
    "Java Developer": {
        "skills": ["Core Java", "API Development"], 
        "tools": ["Spring Boot", "Maven"], "time": "5–8 months",
        "resources": [{"name": "NPTEL Java", "url": "https://nptel.ac.in/courses/106105191"}]
    }
}

# ---------------- CORE AI LOGIC (NLP) ----------------
def get_scores(text):
    """Calculates similarity using TF-IDF and Cosine Similarity"""
    career_profiles = [" ".join(v) for v in CAREERS.values()]
    corpus = [text.lower()] + career_profiles
    vec = TfidfVectorizer(stop_words='english')
    matrix = vec.fit_transform(corpus)
    similarity = cosine_similarity(matrix[0:1], matrix[1:])[0]
    scores = {career: round(similarity[i] * 100, 2) for i, career in enumerate(CAREERS.keys())}
    return dict(sorted(scores.items(), key=lambda x: x[1], reverse=True))

def extract_text_from_file(file):
    """Robust extraction logic to prevent PDF reading errors"""
    filename = file.filename.lower()
    try:
        file.seek(0)
        file_bytes = file.read()
        if not file_bytes: return ""
        file_stream = io.BytesIO(file_bytes)
        if filename.endswith(".pdf"):
            text = extract_text(file_stream)
            return " ".join(text.split())
        elif filename.endswith(".docx"):
            doc = docx.Document(file_stream)
            return " ".join([p.text for p in doc.paragraphs])
    except Exception as e:
        print(f"Extraction Error: {e}")
        return ""
    return ""

# ---------------- ROUTES ----------------

@app.route("/")
def welcome(): 
    return render_template("welcome.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        u, p = request.form["username"], request.form["password"]
        if u == "admin" and p == "admin123":
            session["admin"] = u
            return redirect(url_for("admin"))
        
        user = students_col.find_one({"username": u})
        if user and user["password"] == p:
            session["user"] = u
            return redirect(url_for("career_guidance"))
        error = "Invalid credentials"
    return render_template("login.html", error=error)

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        u, e, p, i = request.form["username"], request.form["email"], request.form["password"], request.form["interest"]
        if students_col.find_one({"username": u}): return "User already exists!"
        students_col.insert_one({"username": u, "email": e, "password": p, "interest": i, "history": []})
        return redirect(url_for("login"))
    return render_template("register.html")

@app.route("/career_guidance", methods=["GET", "POST"])
def career_guidance():
    if "user" not in session: return redirect(url_for("login"))
    result = roadmap = error = best_career = None
    if request.method == "POST":
        skills = request.form.get("skills", "").lower().strip()
        if skills:
            result = get_scores(skills)
            best_career = list(result.keys())[0]
            roadmap = CAREER_ROADMAP.get(best_career)
        else: error = "Please enter skills"
    return render_template("career_guidance.html", result=result, roadmap=roadmap, error=error, best_career=best_career)

@app.route("/resume_screening", methods=["GET", "POST"])
def resume_screening():
    if "user" not in session: return redirect(url_for("login"))
    result = error = None
    if request.method == "POST":
        resume = request.files.get("resume")
        if resume and resume.filename != "":
            text = extract_text_from_file(resume)
            if text and text.strip():
                scores = get_scores(text)
                best_career, best_score = list(scores.items())[0]
                
                word_count = len(text.split())
                ats_bonus = 15 if (200 < word_count < 700) else 5
                ats_score = min(100, (best_score * 0.85) + ats_bonus)

                result = {
                    "career": best_career, 
                    "score": best_score, 
                    "ats_score": round(ats_score, 2), 
                    "top_3": list(scores.items())[:3],
                    "word_count": word_count 
                }
                
                students_col.update_one(
                    {"username": session["user"]}, 
                    {"$push": {"history": {
                        "career": best_career, 
                        "ats": round(ats_score, 2), 
                        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M")
                    }}}
                )
            else: error = "Could not read file."
    return render_template("resume_screening.html", result=result, error=error)

@app.route("/admin")
def admin():
    if "admin" not in session: return redirect(url_for("login"))
    
    total_users = students_col.count_documents({})
    all_users = list(students_col.find({}, {"history": 1}))
    
    career_distribution = {career: 0 for career in CAREERS.keys()}
    total_screenings = 0
    
    for u in all_users:
        user_history = u.get('history', [])
        total_screenings += len(user_history)
        for entry in user_history:
            c_name = entry.get('career')
            if c_name in career_distribution:
                career_distribution[c_name] += 1
    
    labels = list(career_distribution.keys())
    values = list(career_distribution.values())
    top = max(career_distribution, key=career_distribution.get) if total_screenings > 0 else "None"
    
    return render_template("admin.html", 
                           analytics={"users": total_users, "resumes": total_screenings}, 
                           career_labels=labels, 
                           career_values=values, 
                           top_career=top)

@app.route("/admin/bulk_screen", methods=["GET", "POST"])
def admin_bulk_screen():
    if "admin" not in session: return redirect(url_for("login"))
    results = []
    if request.method == "POST":
        jd = request.form.get("jd")
        files = request.files.getlist("resumes")
        for f in files:
            text = extract_text_from_file(f)
            if text:
                corpus = [text.lower(), jd.lower()]
                vec = TfidfVectorizer(stop_words='english')
                matrix = vec.fit_transform(corpus)
                sim = cosine_similarity(matrix[0:1], matrix[1:2])[0][0]
                results.append({"name": f.filename, "score": round(sim * 100, 2)})
        results = sorted(results, key=lambda x: x['score'], reverse=True)
    return render_template("admin_bulk.html", results=results)

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("welcome"))

if __name__ == "__main__":
    app.run(debug=True)