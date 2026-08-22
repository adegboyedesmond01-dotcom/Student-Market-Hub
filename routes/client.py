from datetime import date

from flask import (Blueprint, abort, flash, g, redirect, render_template,
                   request, url_for)

from auth_utils import role_required
from db import get_db, query, scalar

client_bp = Blueprint("client", __name__, url_prefix="/client")

CATEGORIES = [
    "Software development", "Web development", "Mobile development",
    "AI & machine learning", "Data analysis", "UI/UX design",
    "Cybersecurity", "Networking", "Database administration",
    "Technical writing", "Digital marketing", "Engineering",
]

DIFFICULTIES = ["beginner", "intermediate", "advanced"]
PROJECT_TYPES = ["experience", "reward", "client"]

MAX_STUDENTS_LIMIT = 20


def _all_skills():
    return query("SELECT id, name FROM skills ORDER BY name")


@client_bp.route("/dashboard")
@role_required("client")
def dashboard():
    uid = g.user["id"]

    stats = {
        "posted": scalar("SELECT COUNT(*) FROM projects WHERE client_id = %s", (uid,)),
        "open": scalar(
            "SELECT COUNT(*) FROM projects WHERE client_id = %s AND status = 'open'", (uid,)),
        "applications": scalar(
            """SELECT COUNT(*) FROM applications a
               JOIN projects p ON p.id = a.project_id
               WHERE p.client_id = %s AND a.status = 'pending'""", (uid,)),
        "awaiting_review": scalar(
            """SELECT COUNT(*) FROM submissions s
               JOIN assignments asg ON asg.id = s.assignment_id
               JOIN projects p ON p.id = asg.project_id
               LEFT JOIN assessments ass ON ass.submission_id = s.id
               WHERE p.client_id = %s AND ass.id IS NULL""", (uid,)),
        "completed": scalar(
            "SELECT COUNT(*) FROM projects WHERE client_id = %s AND status = 'completed'", (uid,)),
    }

    profile = query(
        "SELECT company_name, website FROM client_profiles WHERE user_id = %s",
        (uid,), one=True) or {}

    recent = query(
        """SELECT id, title, status, deadline, created_at
           FROM projects WHERE client_id = %s
           ORDER BY created_at DESC LIMIT 5""", (uid,))

    return render_template("client/dashboard.html", stats=stats,
                           profile=profile, recent=recent)


@client_bp.route("/projects")
@role_required("client")
def projects():
    rows = query(
        """SELECT p.id, p.title, p.category, p.difficulty, p.project_type,
                  p.budget, p.deadline, p.max_students, p.status, p.created_at,
                  (SELECT COUNT(*) FROM applications a
                    WHERE a.project_id = p.id AND a.status = 'pending')
                    AS pending_applications,
                  (SELECT string_agg(s.name, ', ' ORDER BY s.name)
                     FROM project_skills ps
                     JOIN skills s ON s.id = ps.skill_id
                    WHERE ps.project_id = p.id) AS skill_list
             FROM projects p
            WHERE p.client_id = %s
            ORDER BY p.created_at DESC""",
        (g.user["id"],))

    return render_template("client/projects.html", projects=rows, today=date.today())


@client_bp.route("/projects/new", methods=["GET", "POST"])
@role_required("client")
def create_project():
    skills = _all_skills()
    form = {"difficulty": "beginner", "project_type": "experience", "max_students": "1"}

    if request.method == "POST":
        form = {k: v.strip() for k, v in request.form.items()}
        picked_skills = request.form.getlist("skills")
        form["skills"] = picked_skills

        title = form.get("title", "")
        description = form.get("description", "")
        category = form.get("category", "")
        difficulty = form.get("difficulty", "")
        project_type = form.get("project_type", "")
        publish_now = "publish" in request.form

        errors = []

        if not 5 <= len(title) <= 255:
            errors.append("Give the project a title between 5 and 255 characters.")
        if len(description) < 30:
            errors.append("Describe the work in at least 30 characters so students know what to build.")
        if category not in CATEGORIES:
            errors.append("Choose a category.")
        if difficulty not in DIFFICULTIES:
            errors.append("Choose a difficulty level.")
        if project_type not in PROJECT_TYPES:
            errors.append("Choose a project type.")

        # Budget only applies to paid types; experience projects are always zero.
        budget = 0
        if project_type in ("reward", "client"):
            try:
                budget = float(form.get("budget") or 0)
            except ValueError:
                budget = -1
            if budget <= 0:
                errors.append("Enter a reward amount greater than zero, or switch to an experience project.")

        deadline = None
        raw_deadline = form.get("deadline", "")
        if not raw_deadline:
            errors.append("Set a deadline.")
        else:
            try:
                deadline = date.fromisoformat(raw_deadline)
                if deadline <= date.today():
                    errors.append("The deadline has to be a future date.")
            except ValueError:
                errors.append("Enter the deadline as a valid date.")

        try:
            max_students = int(form.get("max_students") or 1)
        except ValueError:
            max_students = 0
        if not 1 <= max_students <= MAX_STUDENTS_LIMIT:
            errors.append(f"Allow between 1 and {MAX_STUDENTS_LIMIT} students on a project.")

        # Only accept skill ids that actually exist, so a tampered form can't
        # write rows that break the foreign key.
        valid_ids = {str(s["id"]) for s in skills}
        skill_ids = [int(sid) for sid in picked_skills if sid in valid_ids]
        if not skill_ids:
            errors.append("Pick at least one required skill.")

        if errors:
            for message in errors:
                flash(message, "error")
            return render_template("client/create_project.html", form=form,
                                   skills=skills, categories=CATEGORIES,
                                   difficulties=DIFFICULTIES,
                                   project_types=PROJECT_TYPES), 400

        status = "open" if publish_now else "draft"

        conn = get_db()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO projects
                       (client_id, title, description, category, difficulty,
                        project_type, budget, deadline, max_students, status)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                       RETURNING id""",
                    (g.user["id"], title, description, category, difficulty,
                     project_type, budget, deadline, max_students, status),
                )
                project_id = cur.fetchone()["id"]

                cur.executemany(
                    "INSERT INTO project_skills (project_id, skill_id) VALUES (%s, %s)",
                    [(project_id, sid) for sid in skill_ids],
                )
            conn.commit()
        except Exception:
            conn.rollback()
            raise

        if publish_now:
            flash("Project published. Students can see it now.", "success")
        else:
            flash("Saved as a draft. Publish it when you're ready.", "success")
        return redirect(url_for("client.projects"))

    return render_template("client/create_project.html", form=form, skills=skills,
                           categories=CATEGORIES, difficulties=DIFFICULTIES,
                           project_types=PROJECT_TYPES)


@client_bp.route("/projects/<int:project_id>/publish", methods=["POST"])
@role_required("client")
def publish_project(project_id):
    # client_id in the WHERE clause is the ownership check — a client cannot
    # publish someone else's project by guessing the id.
    conn = get_db()
    with conn.cursor() as cur:
        cur.execute(
            """UPDATE projects SET status = 'open'
                WHERE id = %s AND client_id = %s AND status = 'draft'""",
            (project_id, g.user["id"]),
        )
        changed = cur.rowcount
    conn.commit()

    if changed:
        flash("Project published. Students can see it now.", "success")
    else:
        flash("That project could not be published.", "error")
    return redirect(url_for("client.projects"))


@client_bp.route("/projects/<int:project_id>/close", methods=["POST"])
@role_required("client")
def close_project(project_id):
    conn = get_db()
    with conn.cursor() as cur:
        cur.execute(
            """UPDATE projects SET status = 'cancelled'
                WHERE id = %s AND client_id = %s AND status IN ('draft','open')""",
            (project_id, g.user["id"]),
        )
        changed = cur.rowcount
    conn.commit()

    flash("Project closed." if changed else "That project could not be closed.",
          "success" if changed else "error")
    return redirect(url_for("client.projects"))

@client_bp.route("/projects/<int:project_id>/applicants")
@role_required("client")
def applicants(project_id):
    project = query(
        """SELECT p.*,
                  (SELECT COUNT(*) FROM assignments a WHERE a.project_id = p.id) AS taken
             FROM projects p WHERE p.id = %s AND p.client_id = %s""",
        (project_id, g.user["id"]), one=True)
    if not project:
        abort(404)

    rows = query(
        """SELECT a.id, a.status, a.cover_letter, a.applied_at,
                  u.id AS student_id, u.fullname,
                  sp.university, sp.department, sp.level,
                  (SELECT COUNT(*) FROM assignments asg
                    WHERE asg.student_id = u.id AND asg.status = 'completed')
                    AS completed_projects
             FROM applications a
             JOIN users u ON u.id = a.student_id
             LEFT JOIN student_profiles sp ON sp.user_id = u.id
            WHERE a.project_id = %s
            ORDER BY CASE a.status WHEN 'pending' THEN 0 ELSE 1 END, a.applied_at""",
        (project_id,))

    return render_template("client/applicants.html", project=project,
                           applicants=rows)


@client_bp.route("/applications/<int:application_id>/accept", methods=["POST"])
@role_required("client")
def accept_application(application_id):
    conn = get_db()
    try:
        with conn.cursor() as cur:
            # Lock the project row so two accepts arriving together cannot both
            # pass the capacity check and overfill the project.
            cur.execute(
                """SELECT a.id, a.project_id, a.student_id, a.status,
                          p.max_students, p.status AS project_status
                     FROM applications a
                     JOIN projects p ON p.id = a.project_id
                    WHERE a.id = %s AND p.client_id = %s
                    FOR UPDATE OF p""",
                (application_id, g.user["id"]),
            )
            row = cur.fetchone()

            if row is None:
                conn.rollback()
                abort(404)

            if row["status"] != "pending":
                conn.rollback()
                flash("That application has already been decided.", "error")
                return redirect(url_for("client.applicants", project_id=row["project_id"]))

            cur.execute("SELECT COUNT(*) AS n FROM assignments WHERE project_id = %s",
                        (row["project_id"],))
            taken = cur.fetchone()["n"]

            if taken >= row["max_students"]:
                conn.rollback()
                flash("Every place on this project is already filled.", "error")
                return redirect(url_for("client.applicants", project_id=row["project_id"]))

            cur.execute("UPDATE applications SET status = 'accepted' WHERE id = %s",
                        (application_id,))
            cur.execute(
                """INSERT INTO assignments (project_id, student_id, status, started_at)
                   VALUES (%s, %s, 'assigned', NOW())
                   ON CONFLICT (project_id, student_id) DO NOTHING""",
                (row["project_id"], row["student_id"]),
            )

            # Once the last place goes, close the project to new applicants.
            if taken + 1 >= row["max_students"]:
                cur.execute("UPDATE projects SET status = 'assigned' WHERE id = %s",
                            (row["project_id"],))
                cur.execute(
                    """UPDATE applications SET status = 'rejected'
                        WHERE project_id = %s AND status = 'pending'""",
                    (row["project_id"],))

        conn.commit()
    except Exception:
        conn.rollback()
        raise

    flash("Student accepted. The project is now on their dashboard.", "success")
    return redirect(url_for("client.applicants", project_id=row["project_id"]))


@client_bp.route("/applications/<int:application_id>/reject", methods=["POST"])
@role_required("client")
def reject_application(application_id):
    conn = get_db()
    with conn.cursor() as cur:
        cur.execute(
            """UPDATE applications a SET status = 'rejected'
                 FROM projects p
                WHERE a.id = %s AND p.id = a.project_id
                  AND p.client_id = %s AND a.status = 'pending'
            RETURNING a.project_id""",
            (application_id, g.user["id"]),
        )
        row = cur.fetchone()
    conn.commit()

    if row is None:
        abort(404)

    flash("Application declined.", "success")
    return redirect(url_for("client.applicants", project_id=row["project_id"]))
