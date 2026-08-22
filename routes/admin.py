from flask import Blueprint, render_template

from auth_utils import role_required
from db import query, scalar

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


@admin_bp.route("/dashboard")
@role_required("admin")
def dashboard():
    stats = {
        "students": scalar("SELECT COUNT(*) FROM users WHERE role = 'student'"),
        "clients": scalar("SELECT COUNT(*) FROM users WHERE role = 'client'"),
        "suspended": scalar("SELECT COUNT(*) FROM users WHERE status = 'suspended'"),
        "projects": scalar("SELECT COUNT(*) FROM projects"),
        "certificates": scalar("SELECT COUNT(*) FROM certificates"),
    }

    recent = query(
        """SELECT fullname, email, role, status, created_at
           FROM users ORDER BY created_at DESC LIMIT 8"""
    )

    return render_template("admin/dashboard.html", stats=stats, recent=recent)
