"""Session helpers and route guards."""

from functools import wraps

from flask import flash, g, redirect, request, session, url_for

from db import query

DASHBOARDS = {
    "student": "student.dashboard",
    "client": "client.dashboard",
    "admin": "admin.dashboard",
}


def load_current_user():
    """Runs before every request; puts the signed-in user on g.user."""
    user_id = session.get("user_id")
    g.user = None
    if user_id:
        g.user = query(
            "SELECT id, fullname, email, role, status FROM users WHERE id = %s",
            (user_id,),
            one=True,
        )
        # Account deleted or suspended while the session was still alive.
        if g.user is None or g.user["status"] == "suspended":
            session.clear()
            g.user = None


def sign_in(user):
    session.clear()
    session["user_id"] = user["id"]
    session["role"] = user["role"]
    session.permanent = False


def dashboard_for(role):
    return url_for(DASHBOARDS.get(role, "auth.login"))


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not g.get("user"):
            flash("Sign in to continue.", "error")
            return redirect(url_for("auth.login", next=request.path))
        return view(*args, **kwargs)

    return wrapped


def role_required(*roles):
    def decorator(view):
        @wraps(view)
        @login_required
        def wrapped(*args, **kwargs):
            if g.user["role"] not in roles:
                flash("That area belongs to a different account type.", "error")
                return redirect(dashboard_for(g.user["role"]))
            return view(*args, **kwargs)

        return wrapped

    return decorator
