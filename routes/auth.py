import re

from flask import (Blueprint, flash, g, redirect, render_template, request,
                   session, url_for)
from werkzeug.security import check_password_hash, generate_password_hash

from auth_utils import dashboard_for, sign_in
from db import get_db, query

auth_bp = Blueprint("auth", __name__)

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[a-zA-Z]{2,}$")
SIGNUP_ROLES = ("student", "client")


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if g.get("user"):
        return redirect(dashboard_for(g.user["role"]))

    form = {"role": "student"}

    if request.method == "POST":
        form = {k: v.strip() for k, v in request.form.items()}
        role = form.get("role", "")
        fullname = form.get("fullname", "")
        email = form.get("email", "").lower()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm", "")

        errors = []
        if role not in SIGNUP_ROLES:
            errors.append("Choose whether you are joining as a student or a client.")
        if len(fullname) < 3:
            errors.append("Enter your full name.")
        if not EMAIL_RE.match(email):
            errors.append("Enter a valid email address.")
        if len(password) < 8:
            errors.append("Password must be at least 8 characters.")
        if password != confirm:
            errors.append("The two passwords do not match.")
        if role == "client" and not form.get("company_name"):
            errors.append("Enter the company or organisation name.")
        if role == "student" and not form.get("university"):
            errors.append("Enter your university.")

        if not errors and query("SELECT id FROM users WHERE email = %s", (email,), one=True):
            errors.append("That email is already registered. Sign in instead.")

        if errors:
            for message in errors:
                flash(message, "error")
            return render_template("auth/register.html", form=form), 400

        conn = get_db()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO users (fullname, email, password, role)
                       VALUES (%s, %s, %s, %s) RETURNING id""",
                    (fullname, email, generate_password_hash(password), role),
                )
                user_id = cur.fetchone()["id"]

                if role == "student":
                    cur.execute(
                        """INSERT INTO student_profiles
                           (user_id, university, department, level, phone)
                           VALUES (%s, %s, %s, %s, %s)""",
                        (user_id, form.get("university"), form.get("department"),
                         form.get("level"), form.get("phone")),
                    )
                else:
                    cur.execute(
                        """INSERT INTO client_profiles
                           (user_id, company_name, website, phone)
                           VALUES (%s, %s, %s, %s)""",
                        (user_id, form.get("company_name"), form.get("website"),
                         form.get("phone")),
                    )
            conn.commit()
        except Exception:
            conn.rollback()
            raise

        sign_in({"id": user_id, "role": role})
        flash("Account created. Welcome to StudentProjectHub.", "success")
        return redirect(dashboard_for(role))

    return render_template("auth/register.html", form=form)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if g.get("user"):
        return redirect(dashboard_for(g.user["role"]))

    email = ""
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        user = query(
            "SELECT id, fullname, password, role, status FROM users WHERE email = %s",
            (email,),
            one=True,
        )

        # Same message either way, so the form cannot be used to discover emails.
        if not user or not check_password_hash(user["password"], password):
            flash("Email or password is incorrect.", "error")
            return render_template("auth/login.html", email=email), 401

        if user["status"] == "suspended":
            flash("This account is suspended. Contact the platform admin.", "error")
            return render_template("auth/login.html", email=email), 403

        sign_in(user)
        flash(f"Signed in as {user['fullname']}.", "success")

        nxt = request.args.get("next")
        if nxt and nxt.startswith("/") and not nxt.startswith("//"):
            return redirect(nxt)
        return redirect(dashboard_for(user["role"]))

    return render_template("auth/login.html", email=email)


@auth_bp.route("/logout", methods=["POST"])
def logout():
    session.clear()
    flash("Signed out.", "success")
    return redirect(url_for("auth.login"))
