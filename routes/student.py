from datetime import date

from flask import (Blueprint, abort, flash, g, redirect, render_template,
                   request, url_for)

from auth_utils import role_required
from db import get_db, query, scalar

student_bp = Blueprint("student", __name__, url_prefix="/student")


@student_bp.route("/dashboard")
@role_required("student")
def dashboard():
    uid = g.user["id"]

    stats = {
        "open_projects": scalar(
            "SELECT COUNT(*) FROM projects WHERE status = 'open' AND deadline >= CURRENT_DATE"),
        "applications": scalar(
            "SELECT COUNT(*) FROM applications WHERE student_id = %s AND status = 'pending'",
            (uid,)),
        "active": scalar(
            """SELECT COUNT(*) FROM assignments
               WHERE student_id = %s AND status IN ('assigned','in_progress','revision')""",
            (uid,)),
        "completed": scalar(
            "SELECT COUNT(*) FROM assignments WHERE student_id = %s AND status = 'completed'",
            (uid,)),
        "certificates": scalar(
            "SELECT COUNT(*) FROM certificates WHERE student_id = %s", (uid,)),
    }

    profile = query(
        "SELECT university, department, level FROM student_profiles WHERE user_id = %s",
        (uid,), one=True) or {}

    active = query(
        """SELECT a.id, a.status, p.title, p.deadline, u.fullname AS client_name
             FROM assignments a
             JOIN projects p ON p.id = a.project_id
             JOIN users u ON u.id = p.client_id
            WHERE a.student_id = %s AND a.status <> 'completed'
            ORDER BY p.deadline""", (uid,))

    return render_template("student/dashboard.html", stats=stats,
                           profile=profile, active=active)


@student_bp.route("/projects")
@role_required("student")
def browse():
    search = request.args.get("q", "").strip()
    category = request.args.get("category", "").strip()

    sql = """SELECT p.id, p.title, p.description, p.category, p.difficulty,
                    p.project_type, p.budget, p.deadline, p.max_students,
                    COALESCE(c.company_name, u.fullname) AS client_name,
                    (SELECT string_agg(s.name, ', ' ORDER BY s.name)
                       FROM project_skills ps JOIN skills s ON s.id = ps.skill_id
                      WHERE ps.project_id = p.id) AS skill_list,
                    (SELECT COUNT(*) FROM assignments asg
                      WHERE asg.project_id = p.id) AS taken,
                    EXISTS (SELECT 1 FROM applications a
                             WHERE a.project_id = p.id AND a.student_id = %s)
                      AS already_applied
               FROM projects p
               JOIN users u ON u.id = p.client_id
               LEFT JOIN client_profiles c ON c.user_id = p.client_id
              WHERE p.status = 'open' AND p.deadline >= CURRENT_DATE"""
    params = [g.user["id"]]

    if search:
        sql += " AND (p.title ILIKE %s OR p.description ILIKE %s)"
        params += [f"%{search}%", f"%{search}%"]
    if category:
        sql += " AND p.category = %s"
        params.append(category)

    sql += " ORDER BY p.created_at DESC"

    projects = query(sql, tuple(params))
    categories = query(
        "SELECT DISTINCT category FROM projects WHERE status = 'open' ORDER BY category")

    return render_template("student/projects.html", projects=projects,
                           categories=categories, search=search, category=category)


def _load_project(project_id):
    return query(
        """SELECT p.*, COALESCE(c.company_name, u.fullname) AS client_name,
                  c.website,
                  (SELECT string_agg(s.name, ', ' ORDER BY s.name)
                     FROM project_skills ps JOIN skills s ON s.id = ps.skill_id
                    WHERE ps.project_id = p.id) AS skill_list,
                  (SELECT COUNT(*) FROM assignments asg
                    WHERE asg.project_id = p.id) AS taken
             FROM projects p
             JOIN users u ON u.id = p.client_id
             LEFT JOIN client_profiles c ON c.user_id = p.client_id
            WHERE p.id = %s""", (project_id,), one=True)


@student_bp.route("/projects/<int:project_id>")
@role_required("student")
def project_detail(project_id):
    project = _load_project(project_id)
    if not project or project["status"] != "open":
        abort(404)

    application = query(
        "SELECT status, applied_at FROM applications WHERE project_id = %s AND student_id = %s",
        (project_id, g.user["id"]), one=True)

    return render_template("student/project_detail.html", project=project,
                           application=application, today=date.today())


@student_bp.route("/projects/<int:project_id>/apply", methods=["POST"])
@role_required("student")
def apply(project_id):
    uid = g.user["id"]
    cover_letter = request.form.get("cover_letter", "").strip()

    project = _load_project(project_id)
    if not project:
        abort(404)

    problem = None
    if project["status"] != "open":
        problem = "This project is no longer accepting applications."
    elif project["deadline"] < date.today():
        problem = "The deadline for this project has passed."
    elif project["taken"] >= project["max_students"]:
        problem = "All the places on this project are taken."
    elif len(cover_letter) < 40:
        problem = "Write at least 40 characters explaining why you're a fit."

    if problem:
        flash(problem, "error")
        return redirect(url_for("student.project_detail", project_id=project_id))

    conn = get_db()
    try:
        with conn.cursor() as cur:
            # ON CONFLICT covers the case where the same student double-submits;
            # the unique key on (project_id, student_id) is what makes it safe.
            cur.execute(
                """INSERT INTO applications (project_id, student_id, cover_letter)
                   VALUES (%s, %s, %s)
                   ON CONFLICT (project_id, student_id) DO NOTHING
                   RETURNING id""",
                (project_id, uid, cover_letter),
            )
            created = cur.fetchone()
        conn.commit()
    except Exception:
        conn.rollback()
        raise

    if created:
        flash("Application sent. The client will review it.", "success")
    else:
        flash("You have already applied for this project.", "error")
    return redirect(url_for("student.project_detail", project_id=project_id))


@student_bp.route("/applications")
@role_required("student")
def applications():
    rows = query(
        """SELECT a.id, a.status, a.cover_letter, a.applied_at,
                  p.id AS project_id, p.title, p.deadline, p.budget, p.status AS project_status,
                  COALESCE(c.company_name, u.fullname) AS client_name
             FROM applications a
             JOIN projects p ON p.id = a.project_id
             JOIN users u ON u.id = p.client_id
             LEFT JOIN client_profiles c ON c.user_id = p.client_id
            WHERE a.student_id = %s
            ORDER BY a.applied_at DESC""", (g.user["id"],))

    return render_template("student/applications.html", applications=rows)
