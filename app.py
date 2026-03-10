from flask import Flask, render_template, request, redirect, session
import sqlite3
from datetime import datetime, timedelta

app = Flask(__name__)
app.secret_key = "mood_secret"

def get_db():
    return sqlite3.connect("moods.db")

def init_db():
    con = get_db()
    cur = con.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password TEXT,
            goal TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            mood TEXT,
            score INTEGER,
            plan TEXT,
            date TEXT
        )
    """)

    con.commit()
    con.close()

def generate_plan(mood, avg_score=None, goal=None):
    mood = mood.lower()

    if mood == "tired":
        score = 2
        plan = ["Light revision", "Watch a short video", "Rest 10 mins"]
    elif mood == "sad":
        score = 3
        plan = ["Read calmly", "Write formulas", "Revise old topic"]
    elif mood == "okay":
        score = 5
        plan = ["Revise one topic", "Solve 5 questions"]
    elif mood == "happy":
        score = 7
        plan = ["Learn new topic", "Solve 10 problems"]
    elif mood == "motivated":
        score = 9
        plan = ["Hard topic", "15 problems", "Mock test"]
    else:
        score = 5
        plan = ["Light revision", "Short practice"]

    if avg_score:
        if avg_score < 4:
            plan = plan[:1]
        elif avg_score > 7:
            plan.append("Extra challenge")

    if goal:
        plan.append(f"Work on your goal: {goal}")

    return plan, score

def get_badges(streak, motivated_days):
    badges = []
    if streak >= 3:
        badges.append("🔥 3-Day Streak")
    if streak >= 7:
        badges.append("🏆 7-Day Streak")
    if motivated_days >= 5:
        badges.append("💪 5 Motivated Days")
    return badges

def daily_tip(avg_score):
    if avg_score is None:
        return "Start your journey today 🌱"
    if avg_score < 4:
        return "Take it easy today. Small steps matter 💙"
    if avg_score > 7:
        return "You're on fire! Push your limits 🔥"
    return "Consistency beats intensity 💪"

@app.route("/", methods=["GET", "POST"])
def home():
    if "user_id" not in session:
        return redirect("/login")

    con = get_db()
    cur = con.cursor()

    cur.execute("SELECT username, goal FROM users WHERE id=?", (session["user_id"],))
    row = cur.fetchone()
    if not row:
        session.clear()
        con.close()
        return redirect("/login")

    username, goal = row

    cur.execute("""
        SELECT score, mood, date FROM history
        WHERE user_id=? ORDER BY id DESC LIMIT 30
    """, (session["user_id"],))
    rows = cur.fetchall()

    scores = [r[0] for r in rows]
    moods = [r[1] for r in rows]
    dates = [r[2][:10] for r in rows]

    avg_score = round(sum(scores) / len(scores), 2) if scores else None

    streak = 0
    today = datetime.now().date()
    seen = set(dates)
    while today.strftime("%d-%m-%Y") in seen:
        streak += 1
        today -= timedelta(days=1)

    motivated_days = moods.count("motivated")
    badges = get_badges(streak, motivated_days)
    tip = daily_tip(avg_score)

    plan = None

    if request.method == "POST":
        if "goal" in request.form:
            new_goal = request.form["goal"]
            cur.execute("UPDATE users SET goal=? WHERE id=?",
                        (new_goal, session["user_id"]))
            con.commit()
            goal = new_goal
        else:
            mood = request.form["mood"]
            plan, score = generate_plan(mood, avg_score, goal)
            cur.execute("""
                INSERT INTO history (user_id, mood, score, plan, date)
                VALUES (?, ?, ?, ?, ?)
            """, (session["user_id"], mood, score, ", ".join(plan),
                  datetime.now().strftime("%d-%m-%Y %H:%M")))
            con.commit()

    cur.execute("""
        SELECT mood, date FROM history
        WHERE user_id=? ORDER BY id DESC LIMIT 5
    """, (session["user_id"],))
    past = cur.fetchall()

    con.close()

    return render_template(
        "index.html",
        username=username,
        goal=goal,
        plan=plan,
        past=past,
        badges=badges,
        tip=tip,
        streak=streak
    )

def get_week_data(user_id):
    con = get_db()
    cur = con.cursor()
    cur.execute("""
        SELECT mood, score, date FROM history
        WHERE user_id=? ORDER BY id DESC LIMIT 7
    """, (user_id,))
    rows = cur.fetchall()
    con.close()
    return rows


@app.route("/summary")
def summary():
    if "user_id" not in session:
        return redirect("/login")

    data = get_week_data(session["user_id"])
    if not data:
        return render_template("summary.html", empty=True)

    scores = [d[1] for d in data]

    avg = round(sum(scores) / len(scores), 2)
    best = max(scores)
    worst = min(scores)

    return render_template(
        "summary.html",
        avg=avg,
        best=best,
        worst=worst,
        total=len(scores),
        data=data
    )

# -------- ADMIN ROUTES --------

@app.route("/admin")
def admin():
    con = get_db()
    cur = con.cursor()
    cur.execute("SELECT id, username FROM users ORDER BY id")
    users = cur.fetchall()
    con.close()
    return render_template("admin.html", users=users)

@app.route("/admin/user/<int:uid>")
def admin_user(uid):
    con = get_db()
    cur = con.cursor()

    cur.execute("SELECT username FROM users WHERE id=?", (uid,))
    user = cur.fetchone()
    if not user:
        con.close()
        return "User not found"

    username = user[0]

    cur.execute("""
        SELECT mood, score, plan, date
        FROM history WHERE user_id=?
        ORDER BY id DESC
    """, (uid,))
    history = cur.fetchall()
    con.close()

    return render_template("user_history.html", username=username, history=history)

# -------- AUTH --------

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        con = get_db()
        cur = con.cursor()
        try:
            cur.execute(
                "INSERT INTO users (username, password) VALUES (?, ?)",
                (request.form["username"], request.form["password"])
            )
            con.commit()
            return redirect("/login")
        except:
            return "Username exists"
    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        con = get_db()
        cur = con.cursor()
        cur.execute(
            "SELECT id FROM users WHERE username=? AND password=?",
            (request.form["username"], request.form["password"])
        )
        user = cur.fetchone()
        if user:
            session["user_id"] = user[0]
            return redirect("/")
        return "Invalid login"
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

if __name__ == "__main__":
    init_db()
    app.run(debug=True)
