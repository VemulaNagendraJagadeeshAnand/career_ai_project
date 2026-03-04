import os
import io
import docx
import certifi
from datetime import datetime
from flask import Flask, render_template, request, redirect, session, url_for
from pymongo import MongoClient
from dotenv import load_dotenv

# NLP & Extraction Libraries
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from pdfminer.high_level import extract_text

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "career_ai_jntuk_2026_project")

# ---------------- DATABASE CONFIGURATION ----------------
uri = os.getenv("MONGO_URI")
ca = certifi.where()

try:
    # Secure connection for MongoDB Atlas
    client = MongoClient(uri, tlsCAFile=ca, serverSelectionTimeoutMS=5000)
    db = client["career_ai_database"]
    students_col = db["students"]
    client.admin.command('ping') 
    print("✅ MongoDB Atlas Connected Successfully")
except Exception as e:
    print(f"❌ Database Connection Error: {e}")

# ---------------- KNOWLEDGE BASE (NLP & Roadmaps) ----------------
CAREERS = {
    "Data Scientist": ["python", "machine learning", "statistics", "sql", "pandas", "data visualization", "scikit-learn", "deep learning"],
    "Web Developer": ["html", "css", "javascript", "react", "node", "express", "mongodb", "angular", "bootstrap", "typescript"],
    "AI Engineer": ["python", "deep learning", "neural networks", "tensorflow", "pytorch", "nlp", "computer vision", "transformers"],
    "Business Analyst": ["excel", "sql", "power bi", "tableau", "communication", "agile", "scrum", "analytics", "jira"],
    "Cybersecurity Analyst": ["networking", "firewalls", "penetration testing", "wireshark", "linux", "siem", "encryption", "ethical hacking"],
    "Cloud Engineer": ["aws", "azure", "docker", "kubernetes", "terraform", "cloud computing", "devops", "linux", "serverless"],
    "Java Developer": ["java", "spring boot", "hibernate", "maven", "microservices", "mysql", "multithreading", "oops", "junit"]
}

ROADMAPS = {
    "Data Scientist": {"time": "6-8 Months", "resources": [{"name": "Python for Data Science", "url": "https://youtu.be/ed6h-MHeoI0"}]},
    "Web Developer": {"time": "4-5 Months", "resources": [{"name": "Full Stack Web Roadmap", "url": "https://youtu.be/zJSY8tJYnC4"}]},
    "AI Engineer": {"time": "8-10 Months", "resources": [{"name": "Deep Learning Guide", "url": "https://youtu.be/7edvI3_y_n8"}]},
    "Business Analyst": {"time": "3-4 Months", "resources": [{"name": "Business Analytics Course", "url": "https://youtu.be/T_vk2X2L_6Q"}]},
    "Cybersecurity Analyst": {"time": "6-12 Months", "resources": [{"name": "Ethical Hacking Course", "url": "https://youtu.be/3Kq1MIfTWCE"}]},
    "Cloud Engineer": {"time": "5-7 Months", "resources": [{"name": "AWS Roadmap", "url": "https://youtu.be/ia720P9H1yY"}]},
    "Java Developer": {"time": "6 Months", "resources": [{"name": "Spring Boot Tutorial", "url": "https://youtu.be/9SGDpanrc8U"}]}
}

# ---------------- CORE AI & EXTRACTION LOGIC ----------------

def extract_text_from_file(file):
    """Handles PDF and DOCX parsing in-memory"""
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
    except Exception as e:
        return ""
    return ""

def get_ai_scores(text, careers_db):
    """NLP Similarity Engine using TF-IDF"""
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

# ---------------- WEB ROUTES ----------------

@app.route("/")
def welcome(): 
    return render_template("welcome.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        u, p = request.form["username"], request.form["password"]
        if u == "admin" and p == "admin123":
            session["admin"] = u
            return redirect(url_for("admin"))
        user = students_col.find_one({"username": u, "password": p})
        if user:
            session["user"] = u
            return redirect(url_for("student_dashboard"))
    return render_template("login.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        u, e, p, i = request.form["username"], request.form["email"], request.form["password"], request.form["interest"]
        if not students_col.find_one({"username": u}):
            students_col.insert_one({"username": u, "email": e, "password": p, "interest": i, "history": []})
            return redirect(url_for("login"))
    return render_template("register.html")

@app.route("/dashboard")
def student_dashboard():
    if "user" not in session: return redirect(url_for("login"))
    user_data = students_col.find_one({"username": session["user"]})
    history = user_data.get("history", [])
    return render_template("student_dashboard.html", user=user_data, history=history)

@app.route("/career_guidance", methods=["GET", "POST"])
def career_guidance():
    if "user" not in session: return redirect(url_for("login"))
    result, roadmap, best_c = None, None, None
    if request.method == "POST":
        skills = request.form.get("skills", "")
        if skills:
            result = get_ai_scores(skills, CAREERS)
            best_c = list(result.keys())[0] if result else None
            roadmap = ROADMAPS.get(best_c)
    return render_template("career_guidance.html", result=result, best_career=best_c, roadmap=roadmap, careers_dict=CAREERS)

@app.route("/resume_screening", methods=["GET", "POST"])
def resume_screening():
    if "user" not in session: return redirect(url_for("login"))
    result = None
    if request.method == "POST":
        file = request.files.get("resume")
        jd = request.form.get("job_description", "")
        if file and file.filename != "":
            text = extract_text_from_file(file)
            if text:
                if jd.strip():
                    corpus = [text.lower(), jd.lower()]
                    vec = TfidfVectorizer(stop_words='english')
                    matrix = vec.fit_transform(corpus)
                    sim = cosine_similarity(matrix[0:1], matrix[1:2])[0][0]
                    ats_score, career_match = round(float(sim) * 100, 2), "Custom Job Description"
                else:
                    scores_data = get_ai_scores(text, CAREERS)
                    career_match, data = list(scores_data.items())[0]
                    ats_score = min(100, (data['score'] * 0.80) + 20)

                result = {
                    "career": career_match, "ats_score": round(ats_score, 2), 
                    "word_count": len(text.split()),
                    "matches": get_ai_scores(text, CAREERS)[career_match]['matches'] if career_match in CAREERS else []
                }
                students_col.update_one(
                    {"username": session["user"]}, 
                    {"$push": {"history": {"career": career_match, "ats": round(ats_score, 2), "timestamp": datetime.now().strftime("%Y-%m-%d")}} }
                )
    return render_template("resume_screening.html", result=result)

@app.route("/admin")
def admin():
    """Aggregates system-wide analytics for the Admin Dashboard"""
    if "admin" not in session: return redirect(url_for("login"))
    
    all_users = list(students_col.find({}, {"history": 1}))
    career_dist = {c: 0 for c in CAREERS.keys()}
    total_screenings = 0
    
    for u in all_users:
        hist = u.get('history', [])
        total_screenings += len(hist)
        for e in hist:
            career_name = e.get('career')
            if career_name in career_dist:
                career_dist[career_name] += 1
    
    top_career = "No Data Yet"
    if total_screenings > 0:
        top_career = max(career_dist, key=career_dist.get)

    return render_template("admin.html", 
                           analytics={"users": len(all_users), "resumes": total_screenings}, 
                           career_labels=list(career_dist.keys()), 
                           career_values=list(career_dist.values()),
                           top_career=top_career)

@app.route("/admin/bulk_screen", methods=["GET", "POST"])
def admin_bulk_screen():
    """Recruiter tool to rank multiple resumes against one JD"""
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
                results.append({"name": f.filename, "score": round(float(sim) * 100, 2)})
    return render_template("admin_bulk.html", results=sorted(results, key=lambda x: x['score'], reverse=True))

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("welcome"))

if __name__ == "__main__":
    app.run(debug=True)