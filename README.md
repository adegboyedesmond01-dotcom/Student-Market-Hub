# StudentProjectHub — Phase 1 (Foundation)

Flask + Supabase (PostgreSQL). This phase ships the whole account layer:
registration for two roles, login/logout, hashed passwords, role guards, and a
dashboard per role. The full database schema for every later phase is already
created, so Phases 2–8 add code only — no migrations.

No XAMPP, no MySQL, no local database. Supabase is the database.

---

## Setup

### 1. Create the tables

Go to your Supabase project → **SQL Editor** → **New query**. Open
`database/schema.sql`, copy all of it, paste it in, click **Run**.

Then open **Table Editor** in the sidebar. You should see 14 tables:
`users`, `student_profiles`, `client_profiles`, `skills`, `projects`,
`applications`, `assignments`, `submissions`, `assessments`, `messages`,
`ratings`, `certificates`, `student_skills`, `project_skills`.

`skills` will already have 25 rows. Everything else is empty. That's correct.

### 2. Get your connection string

Supabase → **Project Settings** → **Database** → **Connection string** → **URI** tab.

Copy the **Session pooler** string (port `5432`). It looks like:

```
postgresql://postgres.abcdefghijklm:[YOUR-PASSWORD]@aws-0-eu-central-1.pooler.supabase.com:5432/postgres
```

Replace `[YOUR-PASSWORD]` with your actual database password — the one you set
when creating the project. If you've forgotten it, reset it on that same page.

> Use the **pooler** string, not the `db.xxxxx.supabase.co` direct one. The
> direct connection is IPv6-only and most home and office networks in Nigeria
> can't reach it. The pooler works over IPv4.

### 3. Create your `.env` file

In the project folder, copy `.env.example` to `.env`:

```powershell
Copy-Item .env.example .env
```

Open `.env` in Notepad and fill in both values:

```
DATABASE_URL=postgresql://postgres.abc...:yourpassword@aws-0-....pooler.supabase.com:5432/postgres
SECRET_KEY=paste-a-long-random-string-here
```

Generate the secret key with:

```powershell
python -c "import secrets; print(secrets.token_hex(32))"
```

`.env` is in `.gitignore`. Never commit it, never paste it into a chat.

### 4. Install and run

```powershell
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python create_admin.py
python app.py
```

Open http://127.0.0.1:5000

---

## What works now

| Route | Who | Does |
|---|---|---|
| `/register` | public | Student or client signup, creates the matching profile row |
| `/login` | public | Signs in, routes to the right dashboard |
| `/logout` | signed in | POST only, so a stray link can't sign you out |
| `/student/dashboard` | student | Open projects, applications, assignments, certificates |
| `/client/dashboard` | client | Projects posted, applications received, awaiting review |
| `/admin/dashboard` | admin | Platform totals and the newest accounts |

Counts read from the real tables — they show 0 until Phases 2 and 3 start
writing to them.

---

## Files

```
app.py            Application factory, blueprint registration, error pages
config.py         Reads .env
db.py             query() / execute() / scalar(), one connection per request
auth_utils.py     load_current_user, sign_in, @login_required, @role_required
routes/auth.py    Register, login, logout
routes/*.py       One blueprint per role
database/schema.sql   Every table for every phase, plus a starter skill list
templates/        Jinja templates, base.html holds the shell
static/css/       Single stylesheet
create_admin.py   One-off script for the first admin
.env              Your secrets (not in git)
```

---

## Security notes

- Passwords are hashed with scrypt via Werkzeug before they ever reach the
  database. Even with your Supabase dashboard open, you can't read them.
- Login gives the same error for a wrong password and an unknown email, so the
  form can't be used to find out which addresses are registered.
- `admin` can't be selected at signup. The form rejects it server-side even if
  someone edits the HTML. Only `create_admin.py` grants it.
- Suspended accounts are signed out on their next request.
- Every query uses bound parameters (`%s`), so user input can't alter the SQL.

**About Row Level Security:** this app connects as the `postgres` role, which
bypasses RLS entirely. That's fine while Flask is the only thing touching the
database. If you ever add a frontend that talks to Supabase directly with the
anon key, you must write RLS policies first — otherwise anyone with the anon
key can read every row in `users`.

---

## Troubleshooting

**`DATABASE_URL is empty`** — `.env` is missing, or it's named `.env.txt`
because Notepad added an extension. In File Explorer turn on
*View → File name extensions* and check.

**`could not translate host name`** — typo in the host, or you used the direct
`db.xxxxx.supabase.co` string instead of the pooler.

**`password authentication failed`** — you left `[YOUR-PASSWORD]` in the string,
or the password contains `@` `:` `/` `?` `#` which need URL-encoding. Simplest
fix: reset the database password to letters and numbers only.

**`relation "users" does not exist`** — step 1 didn't run. Check the Table
Editor.

---

## Next: Phase 2 (Student)

Profile editing, skills, browse projects with filters, project detail page,
apply with a cover letter, application status list.
