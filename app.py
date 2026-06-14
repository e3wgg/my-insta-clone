import os
from flask import Flask
from extensions import db, login_manager
from config import (SECRET_KEY, SQLALCHEMY_DATABASE_URI, SQLALCHEMY_TRACK_MODIFICATIONS,
                    UPLOAD_FOLDER, MAX_CONTENT_LENGTH, ADMIN_SECRET_PATH,
                    SQLALCHEMY_ENGINE_OPTIONS)

# ── App factory ──────────────────────────────────────────────
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

# ── طرد المبنّد فوراً من أي صفحة ────────────────────────────
@app.before_request
def check_banned():
    from flask import request, redirect, url_for
    from flask_login import current_user
    # استثن صفحات تسجيل الدخول والدعم والأدمن
    excluded = ['/login', '/logout', '/welcome', '/support', '/static',
                f'/{ADMIN_SECRET_PATH}']
    path = request.path
    if any(path.startswith(e) for e in excluded):
        return
    if current_user.is_authenticated and current_user.is_banned:
        from flask_login import logout_user
        logout_user()
        return redirect('/login?banned=1')

# ── Import models (needed for db.create_all) ─────────────────
from models import User  # noqa: F401  (imports all models transitively)

# ── User loader ──────────────────────────────────────────────
@login_manager.user_loader
def load_user(user_id):
    try:
        user = db.session.get(User, int(user_id))
        if user and getattr(user, 'is_banned', False):
            return None
        return user
    except Exception:
        try:
            from sqlalchemy import text
            with db.engine.connect() as conn:
                new_cols = [
                    ('email',           'VARCHAR(150)'),
                    ('email_verified',  'BOOLEAN DEFAULT FALSE'),
                    ('verify_token',    'VARCHAR(64)'),
                    ('is_banned',       'BOOLEAN DEFAULT FALSE'),
                    ('is_admin',        'BOOLEAN DEFAULT FALSE'),
                    ('email_otp',       'VARCHAR(6)'),
                    ('otp_expires_at',  'TIMESTAMP'),
                    ('is_private',      'BOOLEAN DEFAULT FALSE'),
                    ('saves_public',    'BOOLEAN DEFAULT TRUE'),
                    ('avatar_url',      'VARCHAR(500)'),
                    ('avatar_public_id','VARCHAR(255)'),
                ]
                for col, typ in new_cols:
                    conn.execute(text(f'ALTER TABLE "user" ADD COLUMN IF NOT EXISTS {col} {typ}'))
                conn.commit()
            db.session.expire_all()
            user = db.session.get(User, int(user_id))
            if user and getattr(user, 'is_banned', False):
                return None
            return user
        except Exception as e:
            print(f"load_user error: {e}")
            return None

# ── Register blueprints ──────────────────────────────────────
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

# ── Redirect /  ──────────────────────────────────────────────
# The feed blueprint already handles "/" — nothing extra needed.

# ── DB init & migration ──────────────────────────────────────
if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        # Auto-migrate new columns
        try:
            from sqlalchemy import text, inspect
            inspector = inspect(db.engine)
            tables = inspector.get_table_names()
            if 'user' in tables:
                u_cols = [c['name'] for c in inspector.get_columns('user')]
                with db.engine.connect() as conn:
                    new_cols = [
                        ('email_otp',       'VARCHAR(6)'),
                        ('otp_expires_at',  'TIMESTAMP'),
                        ('is_private',      'BOOLEAN DEFAULT FALSE'),
                        ('saves_public',    'BOOLEAN DEFAULT TRUE'),
                        ('avatar_url',      'VARCHAR(500)'),
                        ('avatar_public_id','VARCHAR(255)'),
                    ]
                    for col, typ in new_cols:
                        if col not in u_cols:
                            conn.execute(text(f'ALTER TABLE "user" ADD COLUMN IF NOT EXISTS {col} {typ}'))
                            print(f"✅ Added user.{col}")
                    conn.commit()
        except Exception as e:
            print(f"Migration note: {e}")
        print("✅ DB ready")

    app.run(host="0.0.0.0", port=5000, debug=True)
