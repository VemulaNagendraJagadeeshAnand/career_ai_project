import os
import io
import docx
import certifi
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, session, url_for, flash
from pymongo import MongoClient
from werkzeug.security import generate_password_hash, check_password_hash

# NLP & Extraction Libraries
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from pdfminer.high_level import extract_text

app = Flask(__name__)
app.secret_key = "career_ai_jntuk_2026_full_v7_secure"
app.permanent_session_lifetime = timedelta(minutes=30)

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

ROADMAPS = {
    "python": "https://www.youtube.com/results?search_query=python+tutorial",
    "machine learning": "https://www.coursera.org/learn/machine-learning",
    "sql": "https://www.khanacademy.org/computing/computer-programming/sql",
    "react": "https://react.dev/learn",
    "aws": "https://aws.amazon.com/training/digital/",
    "docker": "https://www.docker.com/101-tutorial/",
    "java": "https://dev.java/learn/"
}

# ---------------- MIDDLEWARE ----------------
@app.after_request
def add_header(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

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
        cp = request.form.get("confirm_password")
        e = request.form.get("email")
        r = request.form.get("role", "student")
        interest = request.form.get("interest")
        # Store security answer in lowercase for easier matching
        ans = request.form.get("security_answer", "").lower().strip()
        
        if p != cp:
            flash("Passwords do not match!", "danger")
            return redirect(url_for("register"))
        if students_col.find_one({"username": u}):
            flash("Username already exists!", "danger")
            return redirect(url_for("register"))
        
        try:
            hashed_pw = generate_password_hash(p)
            students_col.insert_one({
                "username": u, "email": e, "password": hashed_pw, 
                "role": r, "interest": interest, "security_answer": ans,
                "history": [], "created_at": datetime.now()
            })
            session.clear()
            flash("Registration Successful! Please login.", "success")
            return redirect(url_for("login"))
        except Exception as err:
            flash(f"Error: {err}", "danger")
            return redirect(url_for("register"))
    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        role_selected = request.form.get("role") 
        u = request.form.get("username") 
        p = request.form.get("password") 
        user = students_col.find_one({"username": u, "role": role_selected})
        
        if user and check_password_hash(user['password'], p):
            session.clear() 
            session.permanent = True
            session[role_selected] = u
            flash(f"Welcome back, {u}!", "info")
            return redirect(url_for("admin") if role_selected == "admin" else url_for("student_dashboard"))
        else:
            flash("Invalid Credentials or Role Selection", "danger")
    return render_template("login.html")

@app.route("/forgot_password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        u = request.form.get("username")
        ans = request.form.get("security_answer", "").lower().strip()
        new_p = request.form.get("new_password")
        confirm_p = request.form.get("confirm_new_password")

        if new_p != confirm_p:
            flash("New passwords do not match!", "warning")
            return redirect(url_for("forgot_password"))

        user = students_col.find_one({"username": u, "security_answer": ans})
        
        if user:
            new_hashed = generate_password_hash(new_p)
            students_col.update_one({"username": u}, {"$set": {"password": new_hashed}})
            flash("Password reset successful! Please login with your new credentials.", "success")
            return redirect(url_for("login"))
        else:
            flash("Identity verification failed. Incorrect Username or Security Answer.", "danger")
            
    return render_template("forgot_password.html")

@app.route("/dashboard")
def student_dashboard():
    if "student" not in session: 
        flash("Please log in first.", "warning")
        return redirect(url_for("login"))
    user_data = students_col.find_one({"username": session["student"]})
    history = user_data.get("history", [])
    recommendation = None
    level = "Novice"
    if history:
        latest = history[-1]
        score = latest.get("ats", 0)
        level = "Platinum" if score > 80 else "Gold" if score > 60 else "Silver" if score > 30 else "Novice"
        missing = latest.get("missing", [])
        if missing:
            recommendation = {"skill": missing[0], "link": ROADMAPS.get(missing[0].lower(), "#")}
    return render_template("student_dashboard.html", user=user_data, history=history, recommendation=recommendation, level=level)

@app.route("/resume_screening", methods=["GET", "POST"])
def resume_screening():
    if "student" not in session: 
        flash("Access Denied. Log in as Student.", "danger")
        return redirect(url_for("login"))
    result = None
    if request.method == "POST":
        file = request.files.get("resume")
        if not file:
            flash("No file selected!", "warning")
            return redirect(request.url)
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
            flash("Analysis Complete!", "success")
        else:
            flash("Text extraction failed.", "danger")
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
    top_career = max(career_dist, key=career_dist.get) if total_screenings > 0 else "N/A"
    return render_template("admin.html", 
        users=all_users, 
        analytics={"users": len(all_users), "resumes": total_screenings}, 
        career_labels=list(career_dist.keys()), 
        career_values=list(career_dist.values()), 
        top_career=top_career)

@app.route("/logout")
def logout():
    session.clear()
    flash("Successfully logged out.", "info")
    return redirect(url_for("login"))

if __name__ == "__main__":
    app.run(debug=True)