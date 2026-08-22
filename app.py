from flask import Flask, g, redirect, render_template, url_for

from auth_utils import dashboard_for, load_current_user
from config import Config
from db import close_db


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    app.teardown_appcontext(close_db)
    app.before_request(load_current_user)

    from routes.admin import admin_bp
    from routes.auth import auth_bp
    from routes.client import client_bp
    from routes.student import student_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(student_bp)
    app.register_blueprint(client_bp)
    app.register_blueprint(admin_bp)

    @app.route("/")
    def home():
        if g.get("user"):
            return redirect(dashboard_for(g.user["role"]))
        return redirect(url_for("auth.login"))

    @app.errorhandler(404)
    def not_found(_):
        return render_template("error.html", code=404,
                               message="That page does not exist."), 404

    @app.errorhandler(500)
    def server_error(_):
        return render_template("error.html", code=500,
                               message="Something broke on our side. Try again."), 500

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=True)
