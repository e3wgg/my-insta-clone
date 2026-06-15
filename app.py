import os
from flask import Flask, request, redirect
from flask_login import current_user, logout_user
from extensions import db, login_manager
from config import (SECRET_KEY, SQLALCHEMY_DATABASE_URI, SQLALCHEMY_TRACK_MODIFICATIONS,
                    UPLOAD_FOLDER, MAX_CONTENT_LENGTH, ADMIN_SECRET_PATH,
                    SQLALCHEMY_ENGINE_OPTIONS)

# ── App ──────────────────────────────────────────────────────
app = Flask(__name__)
app.config["SECRET_KEY"]                     = SECRET_KEY
app.config["SQLALCHEMY_DATABASE_URI"]        = SQLALCHEMY_DATABASE_URI
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = SQLALCHEMY_TRACK_MODIFICATIONS
app.config["SQLALCHEMY_ENGINE_OPTIONS"]      = SQLALCHEMY_ENGINE_OPTIONS
app.config["UPLOAD_FOLDER"]                  = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"]             = MAX_CONTENT_LENGTH

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

db.init_app(app)
login_manager.init_app(app)

# ── Models ───────────────────────────────────────────────────
from models import User  # noqa — imports all models

# ── DB Setup: run once on first request ──────────────────────
_db_ready = False

def _run_migrations():
    """Create tables + add any missing columns — safe to run on PostgreSQL."""
    from sqlalchemy import text
    db.create_all()
    with db.engine.connect() as conn:
        # user table columns
        for col, typ in [
            ('email',            'VARCHAR(150)'),
            ('email_verified',   'BOOLEAN DEFAULT FALSE'),
            ('verify_token',     'VARCHAR(64)'),
            ('is_banned',        'BOOLEAN DEFAULT FALSE'),
            ('is_admin',         'BOOLEAN DEFAULT FALSE'),
            ('is_private',       'BOOLEAN DEFAULT FALSE'),
            ('saves_public',     'BOOLEAN DEFAULT TRUE'),
            ('avatar_url',       'VARCHAR(500)'),
            ('avatar_public_id', 'VARCHAR(255)'),
            ('email_otp',        'VARCHAR(6)'),
            ('otp_expires_at',   'TIMESTAMP'),
        ]:
            try:
                conn.execute(text(
                    f'ALTER TABLE "user" ADD COLUMN IF NOT EXISTS "{col}" {typ}'
                ))
            except Exception:
                pass
        # message table
        for col, typ in [
            ('image_url',        'VARCHAR(500)'),
            ('image_public_id',  'VARCHAR(255)'),
            ('resource_type',    'VARCHAR(10)'),
            ('is_read',          'BOOLEAN DEFAULT FALSE'),
        ]:
            try:
                conn.execute(text(
                    f'ALTER TABLE message ADD COLUMN IF NOT EXISTS "{col}" {typ}'
                ))
            except Exception:
                pass
        conn.commit()
    print("✅ DB migrations done")


@app.before_request
def setup_once():
    global _db_ready
    if not _db_ready:
        try:
            _run_migrations()
            _db_ready = True
        except Exception as e:
            print(f"Migration error: {e}")

# ── Ban check ─────────────────────────────────────────────────
@app.before_request
def check_banned():
    excluded = ['/login', '/logout', '/welcome', '/support', '/static',
                '/register', '/verify-otp', '/resend-otp',
                f'/{ADMIN_SECRET_PATH}']
    if any(request.path.startswith(e) for e in excluded):
        return
    if current_user.is_authenticated and getattr(current_user, 'is_banned', False):
        logout_user()
        return redirect('/login?banned=1')

# ── User loader ───────────────────────────────────────────────
@login_manager.user_loader
def load_user(user_id):
    try:
        user = db.session.get(User, int(user_id))
        if user and getattr(user, 'is_banned', False):
            return None
        return user
    except Exception as e:
        print(f"load_user error: {e}")
        return None

# ── Blueprints ────────────────────────────────────────────────
from routes.auth     import auth
from routes.feed     import feed
from routes.profile  import profile
from routes.messages import messages
from routes.support  import support
from routes.admin    import admin_bp

app.register_blueprint(auth)
app.register_blueprint(feed)
app.register_blueprint(profile)
app.register_blueprint(messages)
app.register_blueprint(support)
app.register_blueprint(admin_bp)

# ── Run ───────────────────────────────────────────────────────
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
