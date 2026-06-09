import os
import secrets
from flask import Flask, request, redirect, url_for, render_template_string, send_from_directory, jsonify, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import (
    LoginManager,
    UserMixin,
    login_user,
    login_required,
    logout_user,
    current_user
)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime, timezone

app = Flask(__name__)
app.config["SECRET_KEY"] = "instagram_classic_v5_final_pure"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(_BASE_DIR, 'uploads')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + os.path.join(_BASE_DIR, "insta_classic_v5.db")

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

db = SQLAlchemy(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "welcome"


# =========================
# Database Models
# =========================

followers = db.Table('followers',
    db.Column('follower_id', db.Integer, db.ForeignKey('user.id')),
    db.Column('followed_id', db.Integer, db.ForeignKey('user.id'))
)

post_likes = db.Table('post_likes',
    db.Column('user_id', db.Integer, db.ForeignKey('user.id')),
    db.Column('post_id', db.Integer, db.ForeignKey('post.id'))
)

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    avatar_filename = db.Column(db.String(255), nullable=True)
    bio = db.Column(db.String(150), nullable=True)
    email = db.Column(db.String(150), nullable=True)
    email_verified = db.Column(db.Boolean, default=False)
    verify_token = db.Column(db.String(64), nullable=True)
    is_banned = db.Column(db.Boolean, default=False)
    is_admin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    followed = db.relationship(
        'User', secondary=followers,
        primaryjoin=(followers.c.follower_id == id),
        secondaryjoin=(followers.c.followed_id == id),
        backref=db.backref('followers', lazy='dynamic'), lazy='dynamic'
    )

    def follow(self, user):
        if not self.is_following(user):
            self.followed.append(user)

    def unfollow(self, user):
        if self.is_following(user):
            self.followed.remove(user)

    def is_following(self, user):
        return self.followed.filter(followers.c.followed_id == user.id).count() > 0

class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=True)
    image_filename = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    author = db.relationship("User", backref="posts")
    
    likes = db.relationship('User', secondary=post_likes, backref=db.backref('liked_posts', lazy='dynamic'))

class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    body = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    post_id = db.Column(db.Integer, db.ForeignKey("post.id"))
    
    author = db.relationship("User", backref="comments")
    post = db.relationship("Post", backref=db.backref("comments", cascade="all, delete-orphan"))

class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    receiver_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    body = db.Column(db.Text, nullable=True)
    image_filename = db.Column(db.String(255), nullable=True)
    timestamp = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    sender = db.relationship("User", foreign_keys=[sender_id], backref="sent_messages")
    receiver = db.relationship("User", foreign_keys=[receiver_id], backref="received_messages")


class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)   # المستقبل
    actor_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)  # الفاعل
    notif_type = db.Column(db.String(20), nullable=False)  # 'like' or 'follow'
    post_id = db.Column(db.Integer, db.ForeignKey("post.id"), nullable=True)
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    user = db.relationship("User", foreign_keys=[user_id], backref="notifications")
    actor = db.relationship("User", foreign_keys=[actor_id], backref="sent_notifications")
    post = db.relationship("Post", backref=db.backref("notifications", cascade="all, delete-orphan"))


@login_manager.user_loader
def load_user(user_id):
    try:
        return User.query.get(int(user_id))
    except Exception:
        try:
            from sqlalchemy import text, inspect
            inspector = inspect(db.engine)
            existing_cols = [c['name'] for c in inspector.get_columns('user')]
            with db.engine.connect() as conn:
                if 'email' not in existing_cols:
                    conn.execute(text("ALTER TABLE user ADD COLUMN email VARCHAR(150)"))
                if 'email_verified' not in existing_cols:
                    conn.execute(text("ALTER TABLE user ADD COLUMN email_verified BOOLEAN DEFAULT 0"))
                if 'verify_token' not in existing_cols:
                    conn.execute(text("ALTER TABLE user ADD COLUMN verify_token VARCHAR(64)"))
                conn.commit()
            return User.query.get(int(user_id))
        except Exception:
            return None

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# =========================
# Instagram Global Layout
# =========================

def get_layout(content_html, active_tab='', title='Instagram'):
    nav_home = 'text-[#125688]' if active_tab == 'home' else 'text-gray-400'
    nav_search = 'text-[#125688]' if active_tab == 'search' else 'text-gray-400'
    nav_add = 'text-[#125688]' if active_tab == 'add' else 'text-gray-400'
    nav_messages = 'text-[#125688]' if active_tab == 'messages' else 'text-gray-400'
    nav_profile = 'text-[#125688]' if active_tab == 'profile' else 'text-gray-400'

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <script src="https://cdn.jsdelivr.net/npm/@tailwindcss/browser@4"></script>
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Oleo+Script&display=swap');
            body {{ background-color: #edeff1; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif; color: #262626; }}
            .insta-header {{ background: linear-gradient(to bottom, #4a8db7, #2a6a96); border-bottom: 1px solid #0f466f; box-shadow: 0 1px 2px rgba(0,0,0,0.2); }}
            .insta-logo-font {{ font-family: 'Oleo Script', cursive; }}
            .v5-btn {{ background: linear-gradient(to bottom, #ffffff, #f4f4f4); border: 1px solid #cccccc; border-radius: 3px; padding: 5px 10px; font-weight: 600; font-size: 12px; color: #444; box-shadow: 0 1px 1px rgba(0,0,0,0.05); text-align: center; display: inline-block; }}
            .v5-btn-blue {{ background: linear-gradient(to bottom, #4f8fc4, #26679c); border-color: #1e527d; color: #fff; text-shadow: 0 -1px 0 rgba(0,0,0,0.2); }}
            .feed-container {{ border-bottom: 1px solid #d3d3d3; background-color: #ffffff; }}
        </style>
        <title>{title}</title>
    </head>
    <body class="pb-16 max-w-md mx-auto bg-[#edeff1] min-h-screen relative shadow-md">

        <header class="insta-header sticky top-0 z-50 text-white h-11 flex items-center justify-between px-3">
            {'<a href="javascript:history.back()" class="text-white text-base opacity-80"><i class="fa-solid fa-chevron-left"></i></a>' if active_tab == 'profile' and title != 'Instagram' else '<span style="width:28px;"></span>'}
            <span class="{'text-base font-bold uppercase tracking-wide' if active_tab == 'profile' and title != 'Instagram' else 'text-2xl insta-logo-font'} text-center flex-1">{title}</span>
            <div class="flex items-center space-x-3 justify-end" style="width:28px;">
                {'<a href="/settings" class="text-white text-base"><i class="fa-solid fa-ellipsis-vertical"></i></a>' if active_tab == 'profile' and title != 'Instagram' else '<a href="/messages" class="text-white text-lg"><i class="fa-regular fa-paper-plane"></i></a>'}
            </div>
        </header>

        <main class="w-full">
            {content_html}
        </main>

        <footer class="fixed bottom-0 left-0 right-0 z-50 max-w-md mx-auto" style="background:linear-gradient(to bottom,#3a3a3a,#1e1e1e); border-top:1px solid #111; height:52px; display:flex; align-items:center; justify-content:space-around;">
            <a href="/" style="display:flex;align-items:center;justify-content:center;width:52px;height:52px;">
                <i class="fa-solid fa-house" style="font-size:20px; color:{'#ffffff' if active_tab=='home' else '#888'};"></i>
            </a>
            <a href="/search" style="display:flex;align-items:center;justify-content:center;width:52px;height:52px;">
                <i class="fa-solid fa-magnifying-glass" style="font-size:20px; color:{'#ffffff' if active_tab=='search' else '#888'};"></i>
            </a>
            <a href="/create-post" style="display:flex;align-items:center;justify-content:center;width:52px;height:52px;">
                <div style="width:40px;height:40px;border-radius:8px;border:2px solid {'#fff' if active_tab=='add' else '#777'};display:flex;align-items:center;justify-content:center;">
                    <i class="fa-regular fa-circle" style="font-size:10px;color:{'#fff' if active_tab=='add' else '#777'};"></i>
                </div>
            </a>
            <a href="/notifications" style="display:flex;align-items:center;justify-content:center;width:52px;height:52px;">
                <i class="fa-regular fa-heart" style="font-size:20px; color:{'#ffffff' if active_tab=='notifications' else '#888'};"></i>
            </a>
            <a href="/user/{current_user.username if current_user.is_authenticated else ''}" style="display:flex;align-items:center;justify-content:center;width:52px;height:52px;">
                <i class="fa-regular fa-user" style="font-size:20px; color:{'#ffffff' if active_tab=='profile' else '#888'};"></i>
            </a>
        </footer>

    </body>
    </html>
    """
    return html


# =========================
# Welcome & Authentication
# =========================

@app.route("/welcome")
def welcome():
    if current_user.is_authenticated:
        return redirect(url_for('feed'))
        
    return render_template_string("""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Pacifico&display=swap');
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body { background-color: #d8dadb; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif; min-height: 100vh; max-width: 480px; margin: 0 auto; overflow-x: hidden; }
            .collage-area { position: relative; width: 100%; height: 66vh; background: linear-gradient(to bottom, #1a1a1a 0%, #2a2a2a 60%, #d8dadb 100%); overflow: hidden; }
            .photo { position: absolute; border: 3px solid white; box-shadow: 2px 4px 12px rgba(0,0,0,0.5); object-fit: cover; background: #555; }
            .logo-wrap { position: absolute; left: 50%; top: 50%; transform: translate(-50%, -50%); text-align: center; z-index: 20; }
            .insta-cam { width: 54px; height: 54px; border: 3px solid white; border-radius: 12px; display: flex; align-items: center; justify-content: center; margin: 0 auto 8px; background: rgba(255,255,255,0.15); }
            .insta-cam i { font-size: 26px; color: white; }
            .logo-text { font-family: 'Pacifico', cursive; font-size: 36px; color: white; text-shadow: 0 2px 8px rgba(0,0,0,0.6); letter-spacing: 1px; }
            .buttons-area { padding: 24px 28px 30px; background-color: #d8dadb; }
            .btn-row { display: flex; align-items: center; background: #efefef; border: 1px solid #c2c2c2; border-radius: 4px; padding: 13px 16px; margin-bottom: 8px; text-decoration: none; color: #333; font-size: 14px; font-weight: 500; box-shadow: 0 1px 2px rgba(0,0,0,0.08); }
            .btn-row:hover { background: #e5e5e5; }
            .btn-icon { font-size: 17px; color: #777; margin-right: 12px; width: 20px; text-align: center; }
            .btn-arrow { font-size: 13px; color: #aaa; margin-left: auto; }
        </style>
        <title>Instagram</title>
    </head>
    <body>
        <div class="collage-area">
            <img class="photo" style="width:130px;height:100px;top:-10px;left:-15px;transform:rotate(-8deg);" src="https://images.unsplash.com/photo-1500648767791-00dcc994a43e?w=300">
            <img class="photo" style="width:110px;height:85px;top:-5px;left:105px;transform:rotate(5deg);" src="https://images.unsplash.com/photo-1488426862026-3ee34a7d66df?w=300">
            <img class="photo" style="width:125px;height:95px;top:-8px;right:-10px;transform:rotate(-4deg);" src="https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=300">
            <img class="photo" style="width:120px;height:90px;top:80px;left:-20px;transform:rotate(6deg);" src="https://images.unsplash.com/photo-1539571696357-5a69c17a67c6?w=300">
            <img class="photo" style="width:115px;height:88px;top:95px;right:-5px;transform:rotate(-7deg);" src="https://images.unsplash.com/photo-1524504388940-b1c1722653e1?w=300">
            <img class="photo" style="width:135px;height:105px;top:175px;left:-10px;transform:rotate(-5deg);" src="https://images.unsplash.com/photo-1517841905240-472988babdf9?w=300">
            <img class="photo" style="width:155px;height:120px;top:165px;left:110px;transform:rotate(3deg);" src="https://images.unsplash.com/photo-1476514525535-07fb3b4ae5f1?w=300">
            <img class="photo" style="width:120px;height:95px;top:180px;right:-15px;transform:rotate(-6deg);" src="https://images.unsplash.com/photo-1494790108377-be9c29b29330?w=300">
            <img class="photo" style="width:130px;height:100px;top:285px;left:-5px;transform:rotate(7deg);" src="https://images.unsplash.com/photo-1502101872923-d48509bff386?w=300">
            <img class="photo" style="width:125px;height:95px;top:295px;right:10px;transform:rotate(-4deg);" src="https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=300">
            <img class="photo" style="width:110px;height:85px;top:370px;left:60px;transform:rotate(5deg);" src="https://images.unsplash.com/photo-1438761681033-6461ffad8d80?w=300">
            <div style="position:absolute;inset:0;background:linear-gradient(to bottom, rgba(0,0,0,0.35) 0%, rgba(0,0,0,0.1) 50%, rgba(216,218,219,0.7) 85%, rgba(216,218,219,1) 100%);z-index:10;"></div>
            <div class="logo-wrap">
                <div class="insta-cam"><i class="fa-brands fa-instagram"></i></div>
                <div class="logo-text">Instagram</div>
            </div>
        </div>
        <div class="buttons-area">
            <a href="/register" class="btn-row">
                <i class="fa-solid fa-circle-plus btn-icon"></i>
                Register
                <i class="fa-solid fa-chevron-right btn-arrow"></i>
            </a>
            <a href="/login" class="btn-row">
                <i class="fa-regular fa-user btn-icon"></i>
                Sign In
                <i class="fa-solid fa-chevron-right btn-arrow"></i>
            </a>
        </div>
    </body>
    </html>
    """)

@app.route("/verify-email/<token>")
def verify_email(token):
    user = User.query.filter_by(verify_token=token).first()
    if user:
        user.email_verified = True
        user.verify_token = None
        db.session.commit()
        success = True
    else:
        success = False
    return render_template_string("""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
        <style>body{background:#d0d3d6;font-family:-apple-system,sans-serif;display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0;}</style>
    </head>
    <body>
        <div style="background:white;border-radius:8px;padding:32px 24px;text-align:center;max-width:320px;box-shadow:0 2px 12px rgba(0,0,0,0.1);">
            {% if success %}
                <i class="fa-solid fa-circle-check" style="font-size:48px;color:#4caf50;margin-bottom:12px;"></i>
                <h2 style="font-size:16px;font-weight:700;color:#222;margin-bottom:8px;">Account Verified!</h2>
                <p style="font-size:12px;color:#666;margin-bottom:16px;">Your email has been verified successfully.</p>
                <a href="/" style="background:linear-gradient(to bottom,#4a8db7,#2a6a96);color:white;padding:10px 24px;border-radius:4px;font-size:13px;font-weight:700;text-decoration:none;">Go to Feed</a>
            {% else %}
                <i class="fa-solid fa-circle-xmark" style="font-size:48px;color:#e74c3c;margin-bottom:12px;"></i>
                <h2 style="font-size:16px;font-weight:700;color:#222;margin-bottom:8px;">Invalid Link</h2>
                <p style="font-size:12px;color:#666;">This verification link is invalid or has already been used.</p>
            {% endif %}
        </div>
    </body>
    </html>
    """, success=success)


@app.route("/verify-pending")
@login_required
def verify_pending():
    return render_template_string("""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
        <style>body{background:#d0d3d6;font-family:-apple-system,sans-serif;display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0;}</style>
    </head>
    <body>
        <div style="background:white;border-radius:8px;padding:32px 24px;text-align:center;max-width:320px;box-shadow:0 2px 12px rgba(0,0,0,0.1);">
            <i class="fa-regular fa-envelope" style="font-size:48px;color:#4a8db7;margin-bottom:12px;"></i>
            <h2 style="font-size:16px;font-weight:700;color:#222;margin-bottom:8px;">Verify Your Email</h2>
            <p style="font-size:12px;color:#666;margin-bottom:6px;">We sent a verification link to:</p>
            <p style="font-size:13px;font-weight:700;color:#333;margin-bottom:16px;">{{ current_user.email }}</p>
            <p style="font-size:11px;color:#999;margin-bottom:20px;">Please check your inbox and click the link to verify your account.</p>
            <a href="/" style="background:linear-gradient(to bottom,#4a8db7,#2a6a96);color:white;padding:10px 24px;border-radius:4px;font-size:13px;font-weight:700;text-decoration:none;display:inline-block;margin-bottom:10px;">Continue to Feed</a>
        </div>
    </body>
    </html>
    """, current_user=current_user)


@app.route("/settings")
@login_required
def settings():
    return render_template_string("""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
        <style>
            body{background:#d8dadb;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Arial,sans-serif;margin:0;}
            .header{background:linear-gradient(to bottom,#4a8db7,#2a6a96);display:flex;align-items:center;height:48px;padding:0 14px;position:sticky;top:0;z-index:10;}
            .setting-row{display:flex;align-items:center;justify-content:space-between;background:#f5f5f5;border-bottom:1px solid #ddd;padding:14px 16px;text-decoration:none;color:#333;}
            .setting-row:first-child{border-top-left-radius:4px;border-top-right-radius:4px;}
            .setting-row:last-child{border-bottom-left-radius:4px;border-bottom-right-radius:4px;border-bottom:none;}
            .row-left{display:flex;align-items:center;gap:12px;font-size:13px;}
            .row-icon{width:20px;text-align:center;color:#777;font-size:15px;}
            .section-title{font-size:11px;font-weight:700;color:#888;text-transform:uppercase;letter-spacing:0.05em;padding:14px 2px 6px;}
        </style>
    </head>
    <body style="max-width:480px;margin:0 auto;">
        <div class="header">
            <a href="javascript:history.back()" style="color:white;font-size:18px;margin-right:14px;"><i class="fa-solid fa-chevron-left"></i></a>
            <span style="color:white;font-weight:700;font-size:15px;letter-spacing:0.04em;text-transform:uppercase;">Settings</span>
        </div>

        <div style="padding:12px 14px 40px;">

            <div class="section-title">Account</div>
            <div style="border:1px solid #d0d0d0;border-radius:4px;overflow:hidden;margin-bottom:14px;">
                <a href="/edit-profile" class="setting-row">
                    <div class="row-left"><i class="fa-regular fa-user row-icon"></i> Edit Profile</div>
                    <i class="fa-solid fa-chevron-right" style="color:#bbb;font-size:12px;"></i>
                </a>
                <a href="/edit-profile" class="setting-row">
                    <div class="row-left"><i class="fa-solid fa-lock row-icon"></i> Change Password</div>
                    <i class="fa-solid fa-chevron-right" style="color:#bbb;font-size:12px;"></i>
                </a>
                {% if current_user.email %}
                <div class="setting-row" style="cursor:default;">
                    <div class="row-left">
                        <i class="fa-regular fa-envelope row-icon"></i>
                        <span>{{ current_user.email }}</span>
                    </div>
                    {% if current_user.email_verified %}
                        <span style="font-size:11px;color:#4caf50;font-weight:700;"><i class="fa-solid fa-circle-check"></i> Verified</span>
                    {% else %}
                        <span style="font-size:11px;color:#e67e22;font-weight:700;">Pending</span>
                    {% endif %}
                </div>
                {% endif %}
            </div>

            <div class="section-title">Support</div>
            <div style="border:1px solid #d0d0d0;border-radius:4px;overflow:hidden;margin-bottom:14px;">
                <div class="setting-row" style="cursor:default;">
                    <div class="row-left"><i class="fa-regular fa-circle-question row-icon"></i> Help Center</div>
                    <i class="fa-solid fa-chevron-right" style="color:#bbb;font-size:12px;"></i>
                </div>
                <div class="setting-row" style="cursor:default;">
                    <div class="row-left"><i class="fa-solid fa-shield row-icon"></i> Privacy Policy</div>
                    <i class="fa-solid fa-chevron-right" style="color:#bbb;font-size:12px;"></i>
                </div>
            </div>

            <div style="border:1px solid #f5c0c0;border-radius:4px;overflow:hidden;">
                <a href="/logout" class="setting-row" style="color:#e74c3c;">
                    <div class="row-left" style="color:#e74c3c;"><i class="fa-solid fa-right-from-bracket row-icon" style="color:#e74c3c;"></i> Log Out</div>
                </a>
            </div>

        </div>
    </body>
    </html>
    """, current_user=current_user)



# ==============================
# ADMIN DASHBOARD
# ==============================

ADMIN_PASSWORD = "admin1234"  # ← غيّر هذا لكلمة سر قوية!

def admin_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('admin_logged_in'):
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    error = None
    if request.method == "POST":
        if request.form.get("password") == ADMIN_PASSWORD:
            session['admin_logged_in'] = True
            return redirect(url_for('admin_dashboard'))
        error = "Wrong password"
    return render_template_string("""
    <!DOCTYPE html><html><head><meta charset="UTF-8">
    <meta name="viewport" content="width=device-width,initial-scale=1">
    <title>Admin Login</title>
    <style>
        *{box-sizing:border-box;margin:0;padding:0}
        body{background:#1a1a2e;display:flex;align-items:center;justify-content:center;min-height:100vh;font-family:-apple-system,sans-serif}
        .card{background:#16213e;border:1px solid #0f3460;border-radius:12px;padding:40px 32px;width:320px;text-align:center;box-shadow:0 8px 32px rgba(0,0,0,0.4)}
        .logo{font-size:32px;margin-bottom:6px}
        h2{color:#e94560;font-size:18px;margin-bottom:4px}
        p{color:#888;font-size:12px;margin-bottom:24px}
        input{width:100%;padding:12px;border-radius:6px;border:1px solid #0f3460;background:#1a1a2e;color:#fff;font-size:14px;margin-bottom:12px;outline:none}
        input:focus{border-color:#e94560}
        button{width:100%;padding:12px;background:#e94560;color:#fff;border:none;border-radius:6px;font-size:14px;font-weight:700;cursor:pointer}
        button:hover{background:#c73652}
        .err{background:#3d0015;border:1px solid #e94560;color:#ff6b8a;padding:8px 12px;border-radius:6px;font-size:12px;margin-bottom:12px}
    </style></head><body>
    <div class="card">
        <div class="logo">🛡️</div>
        <h2>Admin Panel</h2>
        <p>Instagram Classic Dashboard</p>
        {% if error %}<div class="err">⚠️ {{ error }}</div>{% endif %}
        <form method="post">
            <input type="password" name="password" placeholder="Admin Password" autofocus required>
            <button type="submit">Enter Dashboard</button>
        </form>
    </div>
    </body></html>
    """, error=error)

@app.route("/admin/logout")
def admin_logout():
    session.pop('admin_logged_in', None)
    return redirect(url_for('admin_login'))

@app.route("/admin")
@admin_required
def admin_dashboard():
    search = request.args.get('q', '').strip()
    if search:
        users = User.query.filter(User.username.ilike(f'%{search}%')).order_by(User.created_at.desc()).all()
    else:
        users = User.query.order_by(User.created_at.desc()).all()

    total_users = User.query.count()
    total_posts = Post.query.count()
    banned_count = User.query.filter_by(is_banned=True).count()

    return render_template_string("""
    <!DOCTYPE html><html><head><meta charset="UTF-8">
    <meta name="viewport" content="width=device-width,initial-scale=1">
    <title>Admin Dashboard</title>
    <style>
        *{box-sizing:border-box;margin:0;padding:0}
        body{background:#f0f2f5;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;color:#333}
        .topbar{background:linear-gradient(135deg,#1a1a2e,#16213e);padding:0 24px;height:56px;display:flex;align-items:center;justify-content:space-between;position:sticky;top:0;z-index:100;box-shadow:0 2px 8px rgba(0,0,0,0.3)}
        .topbar h1{color:#fff;font-size:18px;font-weight:700}
        .topbar a{color:#aaa;font-size:13px;text-decoration:none;padding:6px 14px;border:1px solid #444;border-radius:4px}
        .topbar a:hover{color:#fff;border-color:#e94560}
        .stats{display:grid;grid-template-columns:repeat(3,1fr);gap:16px;padding:20px 24px 0}
        .stat{background:#fff;border-radius:10px;padding:20px;text-align:center;box-shadow:0 1px 4px rgba(0,0,0,0.08)}
        .stat-num{font-size:32px;font-weight:800;color:#1a1a2e}
        .stat-lbl{font-size:12px;color:#888;margin-top:4px;text-transform:uppercase;letter-spacing:0.05em}
        .stat.red .stat-num{color:#e94560}
        .section{padding:20px 24px}
        .section-title{font-size:13px;font-weight:700;color:#888;text-transform:uppercase;letter-spacing:0.05em;margin-bottom:12px}
        .search-bar{display:flex;gap:8px;margin-bottom:16px}
        .search-bar input{flex:1;padding:10px 14px;border:1px solid #ddd;border-radius:6px;font-size:13px;outline:none}
        .search-bar input:focus{border-color:#4a8db7}
        .search-bar button{padding:10px 16px;background:#4a8db7;color:#fff;border:none;border-radius:6px;font-size:13px;font-weight:700;cursor:pointer}
        table{width:100%;background:#fff;border-radius:10px;box-shadow:0 1px 4px rgba(0,0,0,0.08);border-collapse:collapse;overflow:hidden}
        th{background:#f8f9fa;padding:12px 14px;text-align:left;font-size:11px;font-weight:700;color:#888;text-transform:uppercase;letter-spacing:0.05em;border-bottom:1px solid #eee}
        td{padding:12px 14px;font-size:13px;border-bottom:1px solid #f5f5f5;vertical-align:middle}
        tr:last-child td{border-bottom:none}
        tr:hover td{background:#fafafa}
        .avatar{width:34px;height:34px;border-radius:50%;object-fit:cover;border:1px solid #ddd}
        .avatar-placeholder{width:34px;height:34px;border-radius:50%;background:#dde;display:inline-flex;align-items:center;justify-content:center;font-size:11px;font-weight:700;color:#556}
        .badge-ban{background:#fff0f0;color:#e94560;border:1px solid #ffc0c0;padding:2px 8px;border-radius:20px;font-size:10px;font-weight:700}
        .badge-ok{background:#f0fff4;color:#27ae60;border:1px solid #b2dfdb;padding:2px 8px;border-radius:20px;font-size:10px;font-weight:700}
        .badge-admin{background:#fff8e1;color:#f39c12;border:1px solid #ffe082;padding:2px 8px;border-radius:20px;font-size:10px;font-weight:700;margin-left:4px}
        .btn{display:inline-block;padding:5px 10px;border-radius:4px;font-size:11px;font-weight:700;text-decoration:none;cursor:pointer;border:none;margin:1px}
        .btn-red{background:#e94560;color:#fff}
        .btn-red:hover{background:#c73652}
        .btn-orange{background:#e67e22;color:#fff}
        .btn-orange:hover{background:#ca6f1e}
        .btn-green{background:#27ae60;color:#fff}
        .btn-green:hover{background:#1e8449}
        .btn-blue{background:#4a8db7;color:#fff}
        .btn-blue:hover{background:#2a6a96}
        .btn-gray{background:#95a5a6;color:#fff}
        .btn-gray:hover{background:#7f8c8d}
        .modal-overlay{display:none;position:fixed;inset:0;background:rgba(0,0,0,0.5);z-index:200;align-items:center;justify-content:center}
        .modal-overlay.active{display:flex}
        .modal{background:#fff;border-radius:12px;padding:28px 24px;width:340px;box-shadow:0 8px 32px rgba(0,0,0,0.2)}
        .modal h3{font-size:16px;font-weight:700;margin-bottom:8px;color:#1a1a2e}
        .modal p{font-size:13px;color:#666;margin-bottom:20px}
        .modal input{width:100%;padding:10px;border:1px solid #ddd;border-radius:6px;font-size:13px;margin-bottom:12px;outline:none}
        .modal input:focus{border-color:#4a8db7}
        .modal-btns{display:flex;gap:8px}
        .modal-btns button{flex:1;padding:10px;border:none;border-radius:6px;font-size:13px;font-weight:700;cursor:pointer}
        .btn-confirm{background:#e94560;color:#fff}
        .btn-cancel{background:#eee;color:#555}
        .posts-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(100px,1fr));gap:8px;margin-top:12px}
        .post-thumb{position:relative;aspect-ratio:1;border-radius:6px;overflow:hidden;background:#ddd}
        .post-thumb img{width:100%;height:100%;object-fit:cover}
        .post-thumb .del-btn{position:absolute;top:4px;right:4px;background:rgba(233,69,96,0.9);color:#fff;border:none;border-radius:4px;padding:2px 6px;font-size:10px;font-weight:700;cursor:pointer}
    </style></head><body>

    <!-- Top Bar -->
    <div class="topbar">
        <h1>🛡️ Admin Dashboard</h1>
        <a href="/admin/logout">Logout</a>
    </div>

    <!-- Stats -->
    <div class="stats">
        <div class="stat">
            <div class="stat-num">{{ total_users }}</div>
            <div class="stat-lbl">Total Users</div>
        </div>
        <div class="stat">
            <div class="stat-num">{{ total_posts }}</div>
            <div class="stat-lbl">Total Posts</div>
        </div>
        <div class="stat red">
            <div class="stat-num">{{ banned_count }}</div>
            <div class="stat-lbl">Banned</div>
        </div>
    </div>

    <!-- Users Table -->
    <div class="section">
        <div class="section-title">Users Management</div>
        <form class="search-bar" method="get">
            <input name="q" value="{{ search }}" placeholder="Search by username..." autocomplete="off">
            <button type="submit">Search</button>
        </form>
        <table>
            <thead>
                <tr>
                    <th>User</th>
                    <th>Email</th>
                    <th>Posts</th>
                    <th>Joined</th>
                    <th>Status</th>
                    <th>Actions</th>
                </tr>
            </thead>
            <tbody>
            {% for u in users %}
                <tr>
                    <td>
                        <div style="display:flex;align-items:center;gap:10px;">
                            {% if u.avatar_filename %}
                                <img src="/uploads/{{ u.avatar_filename }}" class="avatar">
                            {% else %}
                                <div class="avatar-placeholder">{{ u.username[:2].upper() }}</div>
                            {% endif %}
                            <div>
                                <div style="font-weight:700;">@{{ u.username }}</div>
                                {% if u.bio %}<div style="font-size:11px;color:#999;">{{ u.bio[:30] }}</div>{% endif %}
                            </div>
                        </div>
                    </td>
                    <td style="color:#888;font-size:12px;">{{ u.email or '—' }}</td>
                    <td style="font-weight:700;">{{ u.posts|length }}</td>
                    <td style="color:#aaa;font-size:12px;">{{ u.created_at.strftime('%Y-%m-%d') }}</td>
                    <td>
                        {% if u.is_banned %}
                            <span class="badge-ban">Banned</span>
                        {% else %}
                            <span class="badge-ok">Active</span>
                        {% endif %}
                        {% if u.is_admin %}<span class="badge-admin">Admin</span>{% endif %}
                    </td>
                    <td>
                        <!-- Ban / Unban -->
                        {% if u.is_banned %}
                            <a href="/admin/unban/{{ u.id }}" class="btn btn-green" onclick="return confirm('Unban @{{ u.username }}?')">Unban</a>
                        {% else %}
                            <a href="/admin/ban/{{ u.id }}" class="btn btn-orange" onclick="return confirm('Ban @{{ u.username }}?')">Ban</a>
                        {% endif %}
                        <!-- Reset Password -->
                        <button class="btn btn-blue" onclick="openReset({{ u.id }}, '{{ u.username }}')">Reset PW</button>
                        <!-- View Posts -->
                        <button class="btn btn-gray" onclick="openPosts({{ u.id }}, '{{ u.username }}')">Posts</button>
                        <!-- Delete Account -->
                        <a href="/admin/delete-user/{{ u.id }}" class="btn btn-red" onclick="return confirm('DELETE @{{ u.username }}? This cannot be undone!')">Delete</a>
                    </td>
                </tr>
            {% endfor %}
            </tbody>
        </table>
    </div>

    <!-- Reset Password Modal -->
    <div class="modal-overlay" id="resetModal">
        <div class="modal">
            <h3>🔑 Reset Password</h3>
            <p id="resetLabel">Set new password for user</p>
            <form id="resetForm" method="post">
                <input type="password" name="new_password" id="newPwInput" placeholder="New password..." required minlength="6">
                <div class="modal-btns">
                    <button type="button" class="btn-cancel" onclick="closeModal('resetModal')">Cancel</button>
                    <button type="submit" class="btn-confirm">Reset</button>
                </div>
            </form>
        </div>
    </div>

    <!-- Posts Modal -->
    <div class="modal-overlay" id="postsModal">
        <div class="modal" style="width:480px;max-width:95vw;">
            <h3>📸 Posts</h3>
            <p id="postsLabel">Loading...</p>
            <div class="posts-grid" id="postsGrid"></div>
            <div style="margin-top:16px;text-align:right;">
                <button class="btn-cancel" style="padding:8px 16px;border:none;border-radius:6px;cursor:pointer;font-weight:700;" onclick="closeModal('postsModal')">Close</button>
            </div>
        </div>
    </div>

    <script>
        function openReset(uid, uname) {
            document.getElementById('resetLabel').textContent = 'Set new password for @' + uname;
            document.getElementById('resetForm').action = '/admin/reset-password/' + uid;
            document.getElementById('newPwInput').value = '';
            document.getElementById('resetModal').classList.add('active');
        }
        function openPosts(uid, uname) {
            document.getElementById('postsLabel').textContent = 'Posts by @' + uname;
            document.getElementById('postsGrid').innerHTML = '<p style="color:#aaa;font-size:12px;">Loading...</p>';
            document.getElementById('postsModal').classList.add('active');
            fetch('/admin/user-posts/' + uid)
                .then(r => r.json())
                .then(data => {
                    if (!data.posts.length) {
                        document.getElementById('postsGrid').innerHTML = '<p style="color:#aaa;font-size:12px;">No posts.</p>';
                        return;
                    }
                    document.getElementById('postsGrid').innerHTML = data.posts.map(p => `
                        <div class="post-thumb">
                            ${p.image ? `<img src="/uploads/${p.image}">` : `<div style="width:100%;height:100%;display:flex;align-items:center;justify-content:center;font-size:10px;color:#aaa;padding:6px;text-align:center;">${p.content}</div>`}
                            <button class="del-btn" onclick="deletePost(${p.id}, this)">✕</button>
                        </div>
                    `).join('');
                });
        }
        function deletePost(pid, btn) {
            if (!confirm('Delete this post?')) return;
            fetch('/admin/delete-post/' + pid, {method:'POST'})
                .then(r => r.json())
                .then(d => { if(d.ok) btn.closest('.post-thumb').remove(); });
        }
        function closeModal(id) {
            document.getElementById(id).classList.remove('active');
        }
        document.querySelectorAll('.modal-overlay').forEach(m => {
            m.addEventListener('click', e => { if(e.target === m) m.classList.remove('active'); });
        });
    </script>
    </body></html>
    """, users=users, total_users=total_users, total_posts=total_posts,
         banned_count=banned_count, search=search)


@app.route("/admin/ban/<int:uid>")
@admin_required
def admin_ban(uid):
    user = User.query.get_or_404(uid)
    user.is_banned = True
    db.session.commit()
    return redirect(url_for('admin_dashboard', q=request.args.get('q','')))

@app.route("/admin/unban/<int:uid>")
@admin_required
def admin_unban(uid):
    user = User.query.get_or_404(uid)
    user.is_banned = False
    db.session.commit()
    return redirect(url_for('admin_dashboard', q=request.args.get('q','')))

@app.route("/admin/delete-user/<int:uid>")
@admin_required
def admin_delete_user(uid):
    user = User.query.get_or_404(uid)
    # Delete avatar file
    if user.avatar_filename:
        try:
            os.remove(os.path.join(app.config['UPLOAD_FOLDER'], user.avatar_filename))
        except Exception:
            pass
    # Delete post images
    for post in user.posts:
        if post.image_filename:
            try:
                os.remove(os.path.join(app.config['UPLOAD_FOLDER'], post.image_filename))
            except Exception:
                pass
    db.session.delete(user)
    db.session.commit()
    return redirect(url_for('admin_dashboard'))

@app.route("/admin/reset-password/<int:uid>", methods=["POST"])
@admin_required
def admin_reset_password(uid):
    user = User.query.get_or_404(uid)
    new_pw = request.form.get("new_password","").strip()
    if new_pw:
        user.password_hash = generate_password_hash(new_pw)
        db.session.commit()
    return redirect(url_for('admin_dashboard'))

@app.route("/admin/delete-post/<int:pid>", methods=["POST"])
@admin_required
def admin_delete_post(pid):
    from flask import jsonify
    post = Post.query.get_or_404(pid)
    if post.image_filename:
        try:
            os.remove(os.path.join(app.config['UPLOAD_FOLDER'], post.image_filename))
        except Exception:
            pass
    db.session.delete(post)
    db.session.commit()
    return jsonify({"ok": True})

@app.route("/admin/user-posts/<int:uid>")
@admin_required
def admin_user_posts(uid):
    from flask import jsonify
    user = User.query.get_or_404(uid)
    posts = [{"id": p.id, "image": p.image_filename, "content": (p.content or '')[:30]} for p in user.posts]
    return jsonify({"posts": posts})


@app.route("/check-username")
def check_username():
    username = request.args.get("username", "").strip().lower()
    if not username:
        return {"available": False, "reason": "empty"}
    exists = User.query.filter_by(username=username).first() is not None
    return {"available": not exists}

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"].strip().lower()
        password = request.form["password"]
        full_name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip().lower()

        if User.query.filter_by(username=username).first():
            return redirect(url_for("register"))

        token = secrets.token_urlsafe(32)
        user = User(username=username, password_hash=generate_password_hash(password), verify_token=token)
        if full_name:
            user.bio = full_name
        if email:
            user.email = email
        db.session.add(user)
        db.session.commit()

        # Handle avatar upload
        file = request.files.get("avatar")
        if file and allowed_file(file.filename):
            filename = secure_filename(f"avatar_{user.id}_{file.filename}")
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            user.avatar_filename = filename
            db.session.commit()

        # Send verification email if email provided
        if email:
            try:
                import smtplib
                from email.mime.text import MIMEText
                verify_url = request.host_url.rstrip('/') + url_for('verify_email', token=token)
                msg = MIMEText(f"""
Hello {username},

Please verify your Instagram account by clicking the link below:

{verify_url}

If you did not create this account, you can ignore this email.

Instagram Team
                """)
                msg['Subject'] = 'Verify your Instagram account'
                msg['From'] = 'noreply@instagram-classic.com'
                msg['To'] = email
                # Note: configure SMTP settings as needed
                # smtp = smtplib.SMTP('localhost')
                # smtp.send_message(msg)
                # smtp.quit()
            except Exception:
                pass

        login_user(user)
        if email and not user.email_verified:
            return redirect(url_for("verify_pending"))
        return redirect(url_for("feed"))

    return render_template_string("""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <script src="https://cdn.jsdelivr.net/npm/@tailwindcss/browser@4"></script>
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Oleo+Script&display=swap');
            .font-logo { font-family: 'Oleo Script', cursive; }
            body { background-color: #dde0e3; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif; }
            .register-header { background: linear-gradient(to bottom, #4a8db7, #2a6a96); }
            .field-row { background: #f5f5f5; border-bottom: 1px solid #d0d0d0; display: flex; align-items: center; padding: 12px 14px; }
            .field-row:first-child { border-top-left-radius: 4px; border-top-right-radius: 4px; border-top: 1px solid #d0d0d0; }
            .field-row:last-child { border-bottom-left-radius: 4px; border-bottom-right-radius: 4px; border-bottom: 1px solid #d0d0d0; }
            .field-icon { color: #888; margin-right: 10px; font-size: 15px; width: 18px; text-align: center; }
            .field-input { background: transparent; border: none; outline: none; font-size: 13px; color: #333; width: 100%; }
            .field-input::placeholder { color: #aaa; }
            .section-label { font-size: 11px; font-weight: 700; color: #666; text-transform: uppercase; letter-spacing: 0.05em; margin: 14px 0 6px 2px; }
            .register-btn { background: linear-gradient(to bottom, #6dbf67, #4caf50); border: 1px solid #3d9140; color: white; font-weight: 700; font-size: 15px; letter-spacing: 0.02em; padding: 14px; border-radius: 4px; width: 100%; box-shadow: 0 2px 4px rgba(0,0,0,0.15); }
            .photo-box { width: 72px; height: 72px; border: 2px dashed #aaa; border-radius: 4px; display: flex; flex-direction: column; align-items: center; justify-content: center; background: #e8e8e8; cursor: pointer; flex-shrink: 0; }
            .photo-box i { font-size: 26px; color: #999; }
            .photo-box span { font-size: 9px; color: #999; font-weight: 700; margin-top: 3px; letter-spacing: 0.05em; }
            .top-card { background: #f5f5f5; border: 1px solid #d0d0d0; border-radius: 4px; display: flex; overflow: hidden; }
            .top-fields { flex: 1; }
            .divider { height: 1px; background: #d0d0d0; }
            .green-dot { width: 10px; height: 10px; background: #7dc832; border-radius: 50%; display: inline-block; margin-left: 2px; }
        </style>
        <title>Register</title>
    </head>
    <body class="min-h-screen max-w-md mx-auto">

        <!-- Header -->
        <div class="register-header flex items-center px-3 h-12 sticky top-0 z-10 shadow">
            <a href="/welcome" class="text-white mr-3 text-lg"><i class="fa-solid fa-chevron-left"></i></a>
            <span class="text-white font-bold text-base tracking-wide uppercase">Register</span>
        </div>

        <div class="p-3 space-y-3 pb-10">

            <!-- Username + Password card with photo -->
            <div class="top-card">
                <div style="width:88px; border-right:1px solid #d0d0d0; display:flex; align-items:center; justify-content:center; background:#eaeaea;">
                    <label for="avatar_upload" class="photo-box" title="Add photo">
                        <i class="fa-regular fa-user"></i>
                        <span>PHOTO</span>
                        <input type="file" id="avatar_upload" name="avatar" accept="image/*" class="hidden">
                    </label>
                </div>
                <div class="top-fields">
                    <div class="field-row" style="border-top:none; border-left:none; border-right:none; border-radius:0;">
                        <i class="fa-regular fa-user field-icon"></i>
                        <input name="username" id="username" placeholder="register" autocomplete="off" required class="field-input">
                        <span class="green-dot" id="username_dot" style="display:none;"></span>
                    </div>
                    <div class="divider"></div>
                    <div class="field-row" style="border:none; border-radius:0;">
                        <i class="fa-solid fa-lock field-icon"></i>
                        <input type="password" name="password" placeholder="Password" required class="field-input">
                    </div>
                </div>
            </div>

            <!-- PROFILE section label -->
            <div class="section-label">Profile</div>

            <!-- Name + Email fields card -->
            <div style="background:#f5f5f5; border:1px solid #d0d0d0; border-radius:4px; overflow:hidden;">
                <div class="field-row" style="border:none; border-bottom:1px solid #d0d0d0; border-radius:0;">
                    <i class="fa-regular fa-id-badge field-icon"></i>
                    <input name="full_name" id="full_name" placeholder="Name" class="field-input">
                </div>
                <div class="field-row" style="border:none; border-radius:0;">
                    <i class="fa-regular fa-envelope field-icon"></i>
                    <input name="email" id="email_input" type="email" placeholder="Email" class="field-input">
                </div>
            </div>

            <!-- Privacy notice -->
            <p style="font-size:11px; color:#666; margin-top:4px;">Your phone number and email address will always remain private.</p>
            <p style="font-size:11px; color:#666;">By clicking Register you are indicating that you have read and agree to the <a href="#" style="color:#3897f0;">Terms of Service</a> and <a href="#" style="color:#3897f0;">Privacy Policy</a>.</p>

            <!-- Register button -->
            <form method="post" id="reg_form" enctype="multipart/form-data">
                <input type="hidden" name="username" id="hidden_username">
                <input type="hidden" name="password" id="hidden_password">
                <input type="hidden" name="full_name" id="hidden_fullname">
                <input type="hidden" name="email" id="hidden_email">
                <div id="username_error" style="display:none;background:#ffe0e0;border:1px solid #f5c0c0;border-radius:4px;padding:8px 12px;font-size:12px;color:#c0392b;margin-bottom:8px;">
                    <i class="fa-solid fa-circle-exclamation" style="margin-right:6px;"></i>This username is not available. Please choose another.
                </div>
                <button type="submit" class="register-btn" id="reg_btn">Register</button>
            </form>

        </div>

        <script>
            let usernameAvailable = false;
            let checkTimer = null;
            const usernameInput = document.getElementById('username');
            const dot = document.getElementById('username_dot');
            const errorBox = document.getElementById('username_error');

            usernameInput.addEventListener('input', function() {
                clearTimeout(checkTimer);
                const val = this.value.trim();
                if (!val) { dot.style.display='none'; errorBox.style.display='none'; return; }
                dot.style.background = '#aaa';
                dot.style.display = 'inline-block';
                checkTimer = setTimeout(() => {
                    fetch('/check-username?username=' + encodeURIComponent(val))
                        .then(r => r.json())
                        .then(data => {
                            if (data.available) {
                                dot.style.background = '#7dc832';
                                errorBox.style.display = 'none';
                                usernameAvailable = true;
                            } else {
                                dot.style.background = '#e74c3c';
                                errorBox.style.display = 'block';
                                usernameAvailable = false;
                            }
                            dot.style.display = 'inline-block';
                        });
                }, 400);
            });

            reg_form.addEventListener('submit', function(e) {
                if (!usernameAvailable && usernameInput.value.trim()) {
                    e.preventDefault();
                    errorBox.style.display = 'block';
                    return;
                }
                document.getElementById('hidden_username').value = usernameInput.value.trim();
                document.getElementById('hidden_password').value = document.querySelector('input[type=password]').value;
                document.getElementById('hidden_fullname').value = document.getElementById('full_name').value;
                document.getElementById('hidden_email').value = document.getElementById('email_input').value;
            });
        </script>

    </body>
    </html>
    """)

@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        username = request.form["username"].strip().lower()
        password = request.form["password"]
        try:
            user = User.query.filter_by(username=username).first()
            if not user or not check_password_hash(user.password_hash, password):
                error = "Incorrect username or password."
            else:
                login_user(user)
                return redirect(url_for("feed"))
        except Exception as e:
            # DB column missing - run migration then retry
            try:
                from sqlalchemy import text, inspect
                inspector = inspect(db.engine)
                existing_cols = [c['name'] for c in inspector.get_columns('user')]
                with db.engine.connect() as conn:
                    if 'email' not in existing_cols:
                        conn.execute(text("ALTER TABLE user ADD COLUMN email VARCHAR(150)"))
                    if 'email_verified' not in existing_cols:
                        conn.execute(text("ALTER TABLE user ADD COLUMN email_verified BOOLEAN DEFAULT 0"))
                    if 'verify_token' not in existing_cols:
                        conn.execute(text("ALTER TABLE user ADD COLUMN verify_token VARCHAR(64)"))
                    conn.commit()
                user = User.query.filter_by(username=username).first()
                if user and check_password_hash(user.password_hash, password):
                    login_user(user)
                    return redirect(url_for("feed"))
                else:
                    error = "Incorrect username or password."
            except Exception as e2:
                error = f"Database error: {e2}"

    return render_template_string("""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <script src="https://cdn.jsdelivr.net/npm/@tailwindcss/browser@4"></script>
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
        <style>
            body { background-color: #d0d3d6; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif; margin: 0; }
            .login-header { background: linear-gradient(to bottom, #4a8db7, #2a6a96); display: flex; align-items: center; height: 48px; padding: 0 12px; position: sticky; top: 0; z-index: 10; box-shadow: 0 1px 3px rgba(0,0,0,0.2); }
            .field-card { background: #f0f0f0; border: 1px solid #c8c8c8; border-radius: 3px; overflow: hidden; }
            .field-row { display: flex; align-items: center; padding: 14px 14px; background: #f0f0f0; }
            .field-divider { height: 1px; background: #c8c8c8; margin: 0; }
            .field-icon { color: #888; margin-right: 10px; font-size: 15px; width: 18px; text-align: center; flex-shrink: 0; }
            .field-input { background: transparent; border: none; outline: none; font-size: 14px; color: #333; width: 100%; }
            .field-input::placeholder { color: #999; }
            .signin-btn { background: linear-gradient(to bottom, #7bc96f, #5aab4e); border: 1px solid #4a9140; color: white; font-weight: 700; font-size: 15px; padding: 14px; border-radius: 3px; width: 100%; cursor: pointer; }
            .insta-icon { width: 52px; height: 52px; border: 2px solid #aaa; border-radius: 10px; display: flex; align-items: center; justify-content: center; background: #e0e0e0; margin: 0 auto 18px; }
            .insta-icon i { font-size: 26px; color: #888; }
        </style>
        <title>Sign In</title>
    </head>
    <body class="min-h-screen max-w-md mx-auto">

        <!-- Header -->
        <div class="login-header">
            <a href="/welcome" style="color:white; font-size:18px; margin-right:12px;"><i class="fa-solid fa-chevron-left"></i></a>
            <span style="color:white; font-weight:700; font-size:15px; letter-spacing:0.04em; text-transform:uppercase;">Sign In</span>
        </div>

        <div style="padding: 28px 16px 20px;">

            <!-- Instagram camera icon -->
            <div class="insta-icon">
                <i class="fa-brands fa-instagram"></i>
            </div>

            <!-- Fields card -->
            <form method="post" style="margin-bottom: 14px;">
                <div class="field-card">
                    <div class="field-row">
                        <i class="fa-regular fa-user field-icon"></i>
                        <input name="username" placeholder="Username or Email" autocomplete="off" required class="field-input">
                    </div>
                    <div class="field-divider"></div>
                    <div class="field-row">
                        <i class="fa-solid fa-lock field-icon"></i>
                        <input type="password" name="password" placeholder="Password" required class="field-input">
                    </div>
                </div>

                {% if error %}
                <div style="margin-top:10px;background:#ffe0e0;border:1px solid #f5c0c0;border-radius:4px;padding:9px 12px;font-size:12px;color:#c0392b;">
                    <i class="fa-solid fa-circle-exclamation" style="margin-right:6px;"></i>{{ error }}
                </div>
                {% endif %}

                <div style="margin-top: 10px;">
                    <button type="submit" class="signin-btn">Sign In</button>
                </div>
            </form>

            <!-- Forgot Password -->
            <div style="text-align:center; margin-top: 18px;">
                <a href="#" style="color: #3a7bbf; font-size: 14px; text-decoration: none;">Forgot Password?</a>
            </div>

        </div>

    </body>
    </html>
    """, error=error)

@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("welcome"))


# =========================
# Home Feed
# =========================

@app.route("/")
@login_required
def feed():
    posts = Post.query.order_by(Post.created_at.desc()).all()
    
    content_html = """
    <div class="mt-0 space-y-0 pb-20">
        {% for post in posts %}
            <div class="feed-container overflow-hidden bg-white mb-2">
                <!-- Post Header -->
                <div class="flex items-center justify-between px-3 py-2 border-b border-gray-100">
                    <div class="flex items-center space-x-2">
                        {% if post.author.avatar_filename %}
                            <img src="{{ url_for('uploaded_file', filename=post.author.avatar_filename) }}" class="w-8 h-8 rounded-full object-cover border border-gray-300">
                        {% else %}
                            <div class="w-8 h-8 rounded-full bg-gray-300 flex items-center justify-center text-[11px] font-bold text-gray-600 uppercase border border-gray-300">
                                {{ post.author.username[:2] }}
                            </div>
                        {% endif %}
                        <div>
                            <a href="{{ url_for('profile', username=post.author.username) }}" class="font-bold text-xs text-gray-900 block leading-tight">{{ post.author.username }}</a>
                            {% if post.author.bio %}
                            <span class="text-[10px] text-gray-400">{{ post.author.bio }}</span>
                            {% endif %}
                        </div>
                    </div>
                    <span class="text-[10px] text-gray-400">10w</span>
                </div>

                <!-- Post Image -->
                {% if post.image_filename %}
                    <a href="{{ url_for('view_post', post_id=post.id) }}" class="block w-full bg-black">
                        <img src="{{ url_for('uploaded_file', filename=post.image_filename) }}" class="w-full h-auto object-cover" style="max-height:380px;">
                    </a>
                {% endif %}

                <!-- Actions -->
                <div class="px-3 pt-2 pb-1 bg-white">
                    <div class="flex items-center space-x-4 mb-1 text-gray-800" style="font-size:22px;">
                        <a href="{{ url_for('like_post', post_id=post.id) }}">
                            {% if current_user in post.likes %}
                                <i class="fa-solid fa-heart text-red-500"></i>
                            {% else %}
                                <i class="fa-regular fa-heart"></i>
                            {% endif %}
                        </a>
                        <i class="fa-regular fa-comment" style="font-size:20px;"></i>
                    </div>

                    <div class="text-[12px] font-bold text-gray-900 mb-1">
                        &#9829; {{ post.likes|length }} likes
                    </div>

                    {% if post.content %}
                        <p class="text-[12px] text-gray-800 leading-snug mb-1">
                            <a href="{{ url_for('profile', username=post.author.username) }}" class="font-bold text-gray-900 mr-1">{{ post.author.username }}</a>{{ post.content }}
                        </p>
                    {% endif %}

                    {% if post.comments %}
                        <a href="{{ url_for('view_post', post_id=post.id) }}" class="text-[11px] text-gray-400 block mb-1">
                            View all {{ post.comments|length }} comments
                        </a>
                        {% for comment in post.comments[-1:] %}
                            <div class="text-[11px] text-gray-800">
                                <span class="font-bold mr-1 text-gray-900">{{ comment.author.username }}</span>{{ comment.body }}
                            </div>
                        {% endfor %}
                    {% endif %}

                    <form action="{{ url_for('comment_post', post_id=post.id) }}" method="post" class="mt-2 flex items-center border-t border-gray-100 pt-1.5">
                        <input name="body" placeholder="Add a comment..." autocomplete="off" required class="w-full text-[12px] p-1 focus:outline-none bg-transparent text-gray-700 placeholder-gray-400">
                        <button class="text-[#3897f0] font-bold text-[12px] pl-2 whitespace-nowrap">Post</button>
                    </form>
                </div>
            </div>
        {% else %}
            <div class="p-8 text-center text-gray-400 text-xs bg-white border border-gray-200">No posts yet.</div>
        {% endfor %}
    </div>
    """
    full_html = get_layout(content_html, active_tab='home')
    return render_template_string(full_html, posts=posts, current_user=current_user)


# =========================
# View Single Post
# =========================

@app.route("/post/<int:post_id>")
@login_required
def view_post(post_id):
    post = Post.query.get_or_404(post_id)
    
    content_html = """
    <div class="mt-2 px-2 pb-20">
        <div class="mb-2">
            <a href="javascript:history.back()" class="v5-btn text-xs text-gray-600 mb-2"><i class="fa-solid fa-chevron-left mr-1"></i> Back</a>
        </div>
        
        <div class="feed-container overflow-hidden shadow-xs bg-white">
            <div class="flex items-center space-x-2 p-2 border-b border-gray-200 bg-[#fcfcfc]">
                {% if post.author.avatar_filename %}
                    <img src="{{ url_for('uploaded_file', filename=post.author.avatar_filename) }}" class="w-7 h-7 rounded-full object-cover">
                {% else %}
                    <div class="w-7 h-7 rounded-full bg-gray-300 flex items-center justify-center text-[10px] font-bold text-gray-600 uppercase border border-gray-400">
                        {{ post.author.username[:2] }}
                    </div>
                {% endif %}
                <a href="{{ url_for('profile', username=post.author.username) }}" class="font-bold text-xs text-gray-800 hover:underline">
                    {{ post.author.username }}
                </a>
            </div>

            {% if post.image_filename %}
                <div class="w-full bg-[#fafafa] flex items-center justify-center">
                    <img src="{{ url_for('uploaded_file', filename=post.image_filename) }}" class="w-full h-auto object-cover">
                </div>
            {% endif %}

            <div class="p-3 bg-white">
                <div class="flex space-x-4 mb-1.5 text-gray-700 text-lg">
                    <a href="{{ url_for('like_post', post_id=post.id) }}">
                        {% if current_user in post.likes %}
                            <i class="fa-solid fa-heart text-red-500"></i>
                        {% else %}
                            <i class="fa-regular fa-heart"></i>
                        {% endif %}
                    </a>
                </div>
                
                <div class="text-[11px] font-bold text-gray-800 mb-1">
                    {{ post.likes|length }} likes
                </div>

                {% if post.content %}
                    <p class="text-xs text-gray-800 leading-normal"><span class="font-bold mr-1 text-gray-900">{{ post.author.username }}</span>{{ post.content }}</p>
                {% endif %}
                
                <div class="mt-2 border-t border-gray-100 pt-1.5 space-y-1">
                    {% for comment in post.comments %}
                        <div class="text-[11px] text-gray-800">
                            <span class="font-bold mr-1 text-gray-900">{{ comment.author.username }}</span>{{ comment.body }}
                        </div>
                    {% endfor %}
                </div>

                <form action="{{ url_for('comment_post', post_id=post.id) }}" method="post" class="mt-2 flex items-center border-t border-gray-200 pt-1">
                    <input name="body" placeholder="Add a comment..." autocomplete="off" required class="w-full text-xs p-1 focus:outline-none bg-transparent">
                    <button class="text-[#3897f0] font-bold text-xs pl-2">Post</button>
                </form>
            </div>
        </div>
    </div>
    """
    full_html = get_layout(content_html, active_tab='', title='Photo')
    return render_template_string(full_html, post=post, current_user=current_user)


# =========================
# Create Post
# =========================

@app.route("/create-post", methods=["GET", "POST"])
@login_required
def create_post():
    if request.method == "POST":
        content = request.form.get("content", "").strip()
        file = request.files.get("photo")
        filename = None

        if file and allowed_file(file.filename):
            filename = secure_filename(f"v5_post_{datetime.now(timezone.utc).timestamp()}_{file.filename}")
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

        if content or filename:
            post = Post(content=content, image_filename=filename, author=current_user)
            db.session.add(post)
            db.session.commit()
        return redirect(url_for("feed"))

    content_html = """
    <div class="p-3 pb-20">
        <div class="bg-white p-4 border border-gray-300 rounded-sm shadow-xs">
            <form method="post" enctype="multipart/form-data" class="space-y-4">
                <div>
                    <label class="block text-[11px] font-bold text-gray-500 mb-1 uppercase">Choose Photo</label>
                    <input type="file" name="photo" accept="image/*" required class="w-full text-xs">
                </div>
                <div>
                    <label class="block text-[11px] font-bold text-gray-500 mb-1 uppercase">Caption</label>
                    <textarea name="content" rows="3" placeholder="Write a caption..." class="w-full p-2 text-xs bg-gray-50 border border-gray-200 rounded-sm focus:outline-none resize-none"></textarea>
                </div>
                <button class="w-full bg-[#125688] text-white py-2 rounded-sm font-bold text-xs uppercase shadow-sm">Share</button>
            </form>
        </div>
    </div>
    """
    full_html = get_layout(content_html, active_tab='add', title='Share Photo')
    return render_template_string(full_html, current_user=current_user)


# =========================
# Search & Explore
# =========================

@app.route("/search")
@login_required
def search():
    q = request.args.get('q', '').strip()
    users = []
    if q:
        users = User.query.filter(User.username.like(f"%{q}%")).all()

    explore_posts = Post.query.order_by(Post.created_at.desc()).all()

    content_html = """
    <div class="p-2 bg-white border-b border-gray-300 sticky top-0 z-10 shadow-3xs">
        <form method="get" class="flex space-x-2">
            <input name="q" value="{{ q }}" placeholder="Search accounts..." class="w-full px-3 py-1.5 text-xs bg-[#f2f2f2] border border-gray-300 rounded-sm focus:outline-none">
            <button class="bg-[#125688] text-white px-3 text-xs rounded-sm font-semibold">Find</button>
        </form>
    </div>

    {% if q %}
    <div class="p-2 space-y-1">
        <div class="text-[10px] font-bold text-gray-400 uppercase px-1 mb-1">Search Results</div>
        {% for u in users %}
            <a href="{{ url_for('profile', username=u.username) }}" class="flex items-center space-x-3 p-2 bg-white rounded-sm border border-gray-200">
                <div class="w-7 h-7 rounded-full bg-gray-300 flex items-center justify-center font-bold text-[10px] uppercase text-gray-600 border border-gray-400">
                    {{ u.username[:2] }}
                </div>
                <span class="text-xs font-bold text-gray-800">@{{ u.username }}</span>
            </a>
        {% else %}
            <p class="p-3 text-xs text-center text-gray-400 bg-white border border-gray-200 rounded-sm">No matching users found.</p>
        {% endfor %}
    </div>
    {% endif %}

    <div class="p-0.5 pb-20 mt-2">
        <div class="text-[11px] font-bold text-gray-500 uppercase tracking-wider px-2 mb-2"><i class="fa-solid fa-fire mr-1 text-[#125688]"></i> Explore / Recent Photos</div>
        <div class="grid grid-cols-3 gap-0.5">
            {% for p in explore_posts %}
                {% if p.image_filename %}
                    <a href="{{ url_for('view_post', post_id=p.id) }}" class="aspect-square bg-gray-200 overflow-hidden relative block group border border-gray-300">
                        <img src="{{ url_for('uploaded_file', filename=p.image_filename) }}" class="w-full h-full object-cover">
                        <div class="absolute inset-0 bg-black/30 opacity-0 group-hover:opacity-100 flex items-center justify-center text-white text-[10px] font-bold transition-all">
                            <span><i class="fa-solid fa-heart"></i> {{ p.likes|length }}</span>
                        </div>
                    </a>
                {% endif %}
            {% else %}
                <div class="col-span-3 p-8 text-center text-gray-400 text-xs bg-white border border-gray-200 rounded-sm">No photos available in explore.</div>
            {% endfor %}
        </div>
    </div>
    """
    full_html = get_layout(content_html, active_tab='search', title='Explore')
    return render_template_string(full_html, users=users, q=q, explore_posts=explore_posts, current_user=current_user)


# =========================
# Profile View (تم إصلاح الكرشة وعرض أعداد المتابعين بشكل صحيح)
# =========================

@app.route("/user/<username>")
@login_required
def profile(username):
    user = User.query.filter_by(username=username).first_or_404()
    show_list = request.args.get('list', None)
    
    posts_count = len(user.posts)
    followers_count = user.followers.count()
    following_count = user.followed.count()
    
    followers_list = user.followers.all()
    following_list = user.followed.all()

    content_html = f"""
    <div style="background:#fff; min-height:100vh; padding-bottom:60px;">

        <!-- Stats Row -->
        <div style="background:#f9f9f9; padding:16px 14px 12px; border-bottom:1px solid #e0e0e0;">
            <div style="display:flex; align-items:center; gap:16px;">
                <!-- Avatar -->
                {{% if user.avatar_filename %}}
                    <img src="{{{{ url_for('uploaded_file', filename=user.avatar_filename) }}}}"
                         style="width:72px;height:72px;border-radius:50%;object-fit:cover;border:2px solid #ccc;flex-shrink:0;">
                {{% else %}}
                    <div style="width:72px;height:72px;border-radius:50%;background:#e0a050;border:2px solid #ccc;display:flex;align-items:center;justify-content:center;font-size:26px;font-weight:700;color:white;flex-shrink:0;">
                        {{{{ user.username[0].upper() }}}}
                    </div>
                {{% endif %}}

                <!-- Numbers -->
                <div style="flex:1;display:flex;justify-content:space-around;text-align:center;">
                    <div>
                        <div style="font-size:18px;font-weight:700;color:#222;">{posts_count}</div>
                        <div style="font-size:11px;color:#888;">posts</div>
                    </div>
                    <a href="?list=followers" style="text-decoration:none;">
                        <div style="font-size:18px;font-weight:700;color:#222;">{followers_count}</div>
                        <div style="font-size:11px;color:#888;">followers</div>
                    </a>
                    <a href="?list=following" style="text-decoration:none;">
                        <div style="font-size:18px;font-weight:700;color:#222;">{following_count}</div>
                        <div style="font-size:11px;color:#888;">following</div>
                    </a>
                </div>
            </div>

            <!-- Name & Bio -->
            <div style="margin-top:10px;">
                <div style="font-size:13px;font-weight:700;color:#222;">{{{{ user.bio or user.username }}}}</div>
                {{% if user.bio %}}
                    <div style="font-size:12px;color:#555;margin-top:2px;">Here's to the crazy ones ...</div>
                {{% endif %}}
            </div>

            <!-- Edit / Follow buttons -->
            <div style="margin-top:10px; display:flex; gap:8px;">
                {{% if user.id == current_user.id %}}
                    <a href="/edit-profile" style="flex:1;text-align:center;background:linear-gradient(to bottom,#fff,#ebebeb);border:1px solid #ccc;border-radius:3px;padding:7px 0;font-size:12px;font-weight:700;color:#444;text-decoration:none;letter-spacing:0.03em;">EDIT YOUR PROFILE</a>
                {{% else %}}
                    {{% if current_user.is_following(user) %}}
                        <a href="{{{{ url_for('unfollow_user', username=user.username) }}}}" style="flex:1;text-align:center;background:linear-gradient(to bottom,#fff,#ebebeb);border:1px solid #ccc;border-radius:3px;padding:7px 0;font-size:12px;font-weight:700;color:#444;text-decoration:none;">Following</a>
                    {{% else %}}
                        <a href="{{{{ url_for('follow_user', username=user.username) }}}}" style="flex:1;text-align:center;background:linear-gradient(to bottom,#4f8fc4,#26679c);border:1px solid #1e527d;border-radius:3px;padding:7px 0;font-size:12px;font-weight:700;color:#fff;text-decoration:none;">Follow</a>
                    {{% endif %}}
                    <a href="{{{{ url_for('chat', user_id=user.id) }}}}" style="flex:1;text-align:center;background:linear-gradient(to bottom,#fff,#ebebeb);border:1px solid #ccc;border-radius:3px;padding:7px 0;font-size:12px;font-weight:700;color:#444;text-decoration:none;">Message</a>
                {{% endif %}}
            </div>
        </div>

        <!-- Followers/Following List -->
        {{% if show_list %}}
            <div style="background:#f0f0f0;border-bottom:1px solid #ddd;padding:8px 16px;display:flex;justify-content:space-between;align-items:center;">
                <span style="font-size:11px;font-weight:700;color:#666;text-transform:uppercase;">{{% if show_list == 'followers' %}}Followed By{{% else %}}Following{{% endif %}}</span>
                <a href="{{{{ url_for('profile', username=user.username) }}}}" style="color:#e44;font-weight:700;font-size:13px;text-decoration:none;">✕</a>
            </div>
            <div style="max-height:180px;overflow-y:auto;background:#fafafa;border-bottom:1px solid #ddd;">
                {{% if show_list == 'followers' %}}
                    {{% for f in followers_list %}}
                        <a href="{{{{ url_for('profile', username=f.username) }}}}" style="display:flex;align-items:center;gap:10px;padding:8px 16px;border-bottom:1px solid #eee;text-decoration:none;">
                            <div style="width:28px;height:28px;border-radius:50%;background:#ccc;display:flex;align-items:center;justify-content:center;font-size:10px;font-weight:700;color:#555;">{{{{ f.username[:2].upper() }}}}</div>
                            <span style="font-size:12px;font-weight:600;color:#333;">@{{{{ f.username }}}}</span>
                        </a>
                    {{% else %}}<p style="padding:12px;font-size:11px;text-align:center;color:#aaa;">Empty.</p>{{% endfor %}}
                {{% else %}}
                    {{% for f in following_list %}}
                        <a href="{{{{ url_for('profile', username=f.username) }}}}" style="display:flex;align-items:center;gap:10px;padding:8px 16px;border-bottom:1px solid #eee;text-decoration:none;">
                            <div style="width:28px;height:28px;border-radius:50%;background:#ccc;display:flex;align-items:center;justify-content:center;font-size:10px;font-weight:700;color:#555;">{{{{ f.username[:2].upper() }}}}</div>
                            <span style="font-size:12px;font-weight:600;color:#333;">@{{{{ f.username }}}}</span>
                        </a>
                    {{% else %}}<p style="padding:12px;font-size:11px;text-align:center;color:#aaa;">Empty.</p>{{% endfor %}}
                {{% endif %}}
            </div>
        {{% endif %}}

        <!-- Tab bar -->
        <div style="display:flex;border-bottom:1px solid #e0e0e0;background:#fff;">
            <div style="flex:1;display:flex;align-items:center;justify-content:center;padding:10px 0;border-bottom:2px solid #3897f0;">
                <i class="fa-solid fa-grip" style="font-size:18px;color:#3897f0;"></i>
            </div>
            <div style="flex:1;display:flex;align-items:center;justify-content:center;padding:10px 0;">
                <i class="fa-solid fa-bars" style="font-size:18px;color:#bbb;"></i>
            </div>
            <div style="flex:1;display:flex;align-items:center;justify-content:center;padding:10px 0;">
                <i class="fa-regular fa-map" style="font-size:18px;color:#bbb;"></i>
            </div>
            <div style="flex:1;display:flex;align-items:center;justify-content:center;padding:10px 0;">
                <i class="fa-regular fa-user" style="font-size:18px;color:#bbb;"></i>
            </div>
        </div>

        <!-- Photo Grid -->
        <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:2px;padding:2px;">
            {{% for post in user.posts %}}
                <a href="{{{{ url_for('view_post', post_id=post.id) }}}}" style="aspect-ratio:1;display:block;overflow:hidden;background:#ddd;position:relative;">
                    {{% if post.image_filename %}}
                        <img src="{{{{ url_for('uploaded_file', filename=post.image_filename) }}}}" style="width:100%;height:100%;object-fit:cover;">
                    {{% else %}}
                        <div style="width:100%;height:100%;display:flex;align-items:center;justify-content:center;font-size:10px;color:#aaa;padding:4px;text-align:center;">{{{{ post.content[:15] }}}}...</div>
                    {{% endif %}}
                </a>
            {{% endfor %}}
        </div>
    </div>
    """
    active_tab = 'profile' if username == current_user.username else ''
    full_html = get_layout(content_html, active_tab=active_tab, title=user.username.upper())
    return render_template_string(full_html, user=user, current_user=current_user, show_list=show_list, followers_list=followers_list, following_list=following_list)


# =========================
# Instagram DM (تم إصلاح المحاذاة يمين ويسار بالكامل وبشكل مريح للطرفين)
# =========================

@app.route("/notifications")
@login_required
def notifications():
    notifs = Notification.query.filter_by(user_id=current_user.id)\
        .order_by(Notification.created_at.desc()).all()
    # mark all as read
    for n in notifs:
        n.is_read = True
    db.session.commit()

    content_html = """
    <div style="background:#fff; min-height:100vh; padding-bottom:60px;">
        <div style="padding:10px 14px 4px; font-size:11px; font-weight:700; color:#888; text-transform:uppercase; letter-spacing:0.05em; border-bottom:1px solid #eee;">
            Notifications
        </div>
        {% if notifs %}
            {% for n in notifs %}
            <div style="display:flex; align-items:center; padding:12px 14px; border-bottom:1px solid #f0f0f0; background:{% if not n.is_read %}#f0f7ff{% else %}#fff{% endif %};">
                <!-- Avatar -->
                <a href="{{ url_for('profile', username=n.actor.username) }}" style="flex-shrink:0; margin-right:12px;">
                    {% if n.actor.avatar_filename %}
                        <img src="{{ url_for('uploaded_file', filename=n.actor.avatar_filename) }}"
                             style="width:42px;height:42px;border-radius:50%;object-fit:cover;border:1px solid #ddd;">
                    {% else %}
                        <div style="width:42px;height:42px;border-radius:50%;background:#d0d3d6;display:flex;align-items:center;justify-content:center;font-size:14px;font-weight:700;color:#555;border:1px solid #ccc;">
                            {{ n.actor.username[:2].upper() }}
                        </div>
                    {% endif %}
                </a>

                <!-- Text -->
                <div style="flex:1; font-size:13px; color:#333; line-height:1.4;">
                    <a href="{{ url_for('profile', username=n.actor.username) }}" style="font-weight:700; color:#222; text-decoration:none;">{{ n.actor.username }}</a>
                    {% if n.notif_type == 'like' %}
                        <span style="color:#555;"> liked your photo.</span>
                    {% elif n.notif_type == 'follow' %}
                        <span style="color:#555;"> started following you.</span>
                    {% endif %}
                    <div style="font-size:10px; color:#aaa; margin-top:2px;">{{ n.created_at.strftime('%b %d') }}</div>
                </div>

                <!-- Thumbnail or follow icon -->
                {% if n.notif_type == 'like' and n.post and n.post.image_filename %}
                    <a href="{{ url_for('view_post', post_id=n.post.id) }}" style="flex-shrink:0; margin-left:10px;">
                        <img src="{{ url_for('uploaded_file', filename=n.post.image_filename) }}"
                             style="width:44px;height:44px;object-fit:cover;border-radius:3px;border:1px solid #ddd;">
                    </a>
                {% elif n.notif_type == 'follow' %}
                    <div style="flex-shrink:0; margin-left:10px; width:44px; height:44px; display:flex; align-items:center; justify-content:center;">
                        <i class="fa-solid fa-user-plus" style="font-size:18px; color:#3897f0;"></i>
                    </div>
                {% elif n.notif_type == 'like' %}
                    <div style="flex-shrink:0; margin-left:10px; width:44px; height:44px; display:flex; align-items:center; justify-content:center;">
                        <i class="fa-solid fa-heart" style="font-size:18px; color:#e74c3c;"></i>
                    </div>
                {% endif %}
            </div>
            {% endfor %}
        {% else %}
            <div style="padding:40px; text-align:center; color:#aaa; font-size:13px;">
                <i class="fa-regular fa-heart" style="font-size:40px; margin-bottom:12px; display:block;"></i>
                No notifications yet
            </div>
        {% endif %}
    </div>
    """
    full_html = get_layout(content_html, active_tab='notifications', title='Activity')
    return render_template_string(full_html, notifs=notifs, current_user=current_user)


@app.route("/messages")
@login_required
def inbox():
    all_users = User.query.filter(User.id != current_user.id).all()
    
    content_html = """
    <div class="p-2 space-y-1.5 pb-20">
        <div class="text-[11px] font-bold text-gray-500 uppercase tracking-wider px-1 mb-1">Direct Inbox</div>
        {% for u in users %}
            <a href="{{ url_for('chat', user_id=u.id) }}" class="flex items-center justify-between p-3 bg-white border border-gray-300 rounded-xs shadow-2xs hover:bg-gray-50 transition">
                <div class="flex items-center space-x-3">
                    {% if u.avatar_filename %}
                        <img src="{{ url_for('uploaded_file', filename=u.avatar_filename) }}" class="w-8 h-8 rounded-full object-cover border border-gray-300">
                    {% else %}
                        <div class="w-8 h-8 rounded-full bg-gray-200 flex items-center justify-center font-bold text-xs uppercase text-gray-600 border border-gray-400">
                            {{ u.username[:2] }}
                        </div>
                    {% endif %}
                    <span class="text-xs font-bold text-gray-800">@{{ u.username }}</span>
                </div>
                <span class="v5-btn text-[10px]">Open</span>
            </a>
        {% else %}
            <p class="p-6 text-xs text-center text-gray-400 bg-white border border-gray-200 rounded-sm">No conversations available.</p>
        {% endfor %}
    </div>
    """
    full_html = get_layout(content_html, active_tab='messages', title='Instagram Direct')
    return render_template_string(full_html, users=all_users, current_user=current_user)

@app.route("/messages/<int:user_id>", methods=["GET", "POST"])
@login_required
def chat(user_id):
    recipient = User.query.get_or_404(user_id)
    
    if request.method == "POST":
        body = request.form.get("body", "").strip()
        file = request.files.get("dm_photo")
        filename = None

        if file and allowed_file(file.filename):
            filename = secure_filename(f"v5_dm_{datetime.now(timezone.utc).timestamp()}_{file.filename}")
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

        if body or filename:
            msg = Message(sender_id=current_user.id, receiver_id=recipient.id, body=body, image_filename=filename)
            db.session.add(msg)
            db.session.commit()
        return redirect(url_for('chat', user_id=user_id))

    messages = Message.query.filter(
        ((Message.sender_id == current_user.id) & (Message.receiver_id == recipient.id)) |
        ((Message.sender_id == recipient.id) & (Message.receiver_id == current_user.id))
    ).order_by(Message.timestamp.asc()).all()

    return render_template_string("""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <script src="https://cdn.jsdelivr.net/npm/@tailwindcss/browser@4"></script>
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
        <style>
            body { background-color: #edeff1; font-family: -apple-system, BlinkMacSystemFont, Arial, sans-serif; }
            .v5-header { background-color: #125688; border-bottom: 1px solid #0f466f; }
            
            /* فقاعة الرسالة الخاصة بي (تظهر يميناً دائماً) */
            .dm-bubble-send { background: linear-gradient(to bottom, #e1f1ff, #d2e9ff); border: 1px solid #baccdc; border-radius: 6px 6px 0px 6px; }
            
            /* فقاعة الرسالة المستلمة من الطرف الآخر (تظهر يساراً دائماً) */
            .dm-bubble-recv { background: linear-gradient(to bottom, #ffffff, #f4f4f4); border: 1px solid #d3d3d3; border-radius: 6px 6px 6px 0px; }
            
            .v5-input { border: 1px solid #cccccc; border-radius: 3px; box-shadow: inset 0 1px 2px rgba(0,0,0,0.05); }
        </style>
        <title>Direct Chat</title>
    </head>
    <body class="max-w-md mx-auto min-h-screen flex flex-col justify-between relative shadow-md bg-[#edeff1]">
        
        <header class="v5-header text-white h-11 flex items-center px-3 sticky top-0 z-50 shadow-sm">
            <a href="/messages" class="text-white opacity-80 mr-3 text-sm"><i class="fa-solid fa-chevron-left"></i> Direct</a>
            <a href="/user/{{ recipient.username }}" class="font-bold text-xs flex-1 text-center pr-8 text-white hover:underline">
                @{{ recipient.username }}
            </a>
        </header>

        <main class="flex-1 p-3 overflow-y-auto space-y-4 pb-24 flex flex-col">
            {% for msg in messages %}
                <div class="w-full flex items-start space-x-2 {% if msg.sender_id == current_user.id %}justify-end flex-row-reverse space-x-reverse{% else %}justify-start{% endif %}">
                    
                    <div class="flex-shrink-0">
                        {% if msg.sender_id == current_user.id %}
                            {% if current_user.avatar_filename %}
                                <img src="{{ url_for('uploaded_file', filename=current_user.avatar_filename) }}" class="w-6 h-6 rounded-full object-cover border border-gray-300 shadow-3xs">
                            {% else %}
                                <div class="w-6 h-6 rounded-full bg-blue-200 border border-blue-400 flex items-center justify-center text-[8px] font-bold text-blue-700 uppercase">
                                    {{ current_user.username[:2] }}
                                </div>
                            {% endif %}
                        {% else %}
                            {% if recipient.avatar_filename %}
                                <img src="{{ url_for('uploaded_file', filename=recipient.avatar_filename) }}" class="w-6 h-6 rounded-full object-cover border border-gray-300 shadow-3xs">
                            {% else %}
                                <div class="w-6 h-6 rounded-full bg-gray-300 border border-gray-400 flex items-center justify-center text-[8px] font-bold text-gray-600 uppercase">
                                    {{ recipient.username[:2] }}
                                </div>
                            {% endif %}
                        {% endif %}
                    </div>

                    <div class="max-w-[72%] px-3 py-2 text-xs shadow-3xs {% if msg.sender_id == current_user.id %}dm-bubble-send text-right{% else %}dm-bubble-recv text-left{% endif %}">
                        {% if msg.image_filename %}
                            <div class="mb-1 rounded-xs overflow-hidden max-w-xs border border-gray-300 inline-block">
                                <img src="{{ url_for('uploaded_file', filename=msg.image_filename) }}" class="w-full h-auto max-h-44 object-cover">
                            </div>
                        {% endif %}
                        
                        {% if msg.body %}
                            <p class="whitespace-pre-wrap leading-relaxed text-gray-800">{{ msg.body }}</p>
                        {% endif %}
                    </div>
                </div>
            {% endfor %}
        </main>

        <div class="fixed bottom-0 left-0 right-0 max-w-md mx-auto bg-[#f6f6f6] border-t border-gray-300 p-2 z-50">
            <form method="post" enctype="multipart/form-data" class="flex flex-col space-y-2">
                <div class="flex items-center space-x-2">
                    <input name="body" placeholder="Write a classic direct message..." autocomplete="off"
                           class="w-full px-3 py-1.5 bg-white v5-input text-xs focus:outline-none">
                    <button class="bg-[#125688] text-white font-bold text-xs px-3 py-1.5 rounded-sm shadow-2xs">Send</button>
                </div>
                <div class="flex items-center px-0.5 justify-between">
                    <label class="cursor-pointer text-[10px] bg-gradient-to-b from-white to-gray-100 hover:to-gray-200 text-gray-700 px-2.5 py-1 border border-gray-300 rounded-sm shadow-3xs font-semibold">
                        <i class="fa-solid fa-camera mr-1 text-gray-500"></i> Attach Photo
                        <input type="file" name="dm_photo" accept="image/*" class="hidden" onchange="alert('Photo ready to send!')">
                    </label>
                    <span class="text-[9px] text-gray-400 font-medium">Classic Instagram DM System</span>
                </div>
            </form>
        </div>

    </body>
    </html>
    """, recipient=recipient, messages=messages, current_user=current_user)


# =========================
# Remaining Global Interactions
# =========================

@app.route("/like/<int:post_id>")
@login_required
def like_post(post_id):
    post = Post.query.get_or_404(post_id)
    if current_user in post.likes:
        post.likes.remove(current_user)
        # remove like notification
        Notification.query.filter_by(user_id=post.user_id, actor_id=current_user.id, notif_type='like', post_id=post_id).delete()
    else:
        post.likes.append(current_user)
        # add like notification (not for own posts)
        if post.user_id != current_user.id:
            exists = Notification.query.filter_by(user_id=post.user_id, actor_id=current_user.id, notif_type='like', post_id=post_id).first()
            if not exists:
                notif = Notification(user_id=post.user_id, actor_id=current_user.id, notif_type='like', post_id=post_id)
                db.session.add(notif)
    db.session.commit()
    return redirect(request.referrer or url_for('feed'))

@app.route("/comment/<int:post_id>", methods=["POST"])
@login_required
def comment_post(post_id):
    body = request.form.get("body", "").strip()
    if body:
        comment = Comment(body=body, user_id=current_user.id, post_id=post_id)
        db.session.add(comment)
        db.session.commit()
    return redirect(request.referrer or url_for('feed'))

@app.route('/debug-uploads')
def debug_uploads():
    folder = app.config['UPLOAD_FOLDER']
    exists = os.path.exists(folder)
    files = os.listdir(folder) if exists else []
    return {
        "upload_folder": folder,
        "folder_exists": exists,
        "files_count": len(files),
        "files": files[:20]
    }

@app.route('/uploads/<path:filename>')
def uploaded_file(filename):
    from flask import Response, abort
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    if os.path.isfile(filepath):
        return send_from_directory(app.config['UPLOAD_FOLDER'], filename)
    # fallback: 1x1 transparent PNG
    import base64
    png = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==')
    return Response(png, mimetype='image/png')

@app.route("/follow/<username>")
@login_required
def follow_user(username):
    user = User.query.filter_by(username=username).first_or_404()
    if user != current_user:
        current_user.follow(user)
        exists = Notification.query.filter_by(user_id=user.id, actor_id=current_user.id, notif_type='follow').first()
        if not exists:
            notif = Notification(user_id=user.id, actor_id=current_user.id, notif_type='follow')
            db.session.add(notif)
        db.session.commit()
    return redirect(url_for('profile', username=username))

@app.route("/unfollow/<username>")
@login_required
def unfollow_user(username):
    user = User.query.filter_by(username=username).first_or_404()
    if user != current_user:
        current_user.unfollow(user)
        Notification.query.filter_by(user_id=user.id, actor_id=current_user.id, notif_type='follow').delete()
        db.session.commit()
    return redirect(url_for('profile', username=username))

@app.route("/edit-profile", methods=["GET", "POST"])
@login_required
def edit_profile():
    if request.method == "POST":
        bio = request.form.get("bio", "").strip()
        file = request.files.get("avatar")
        
        if file and allowed_file(file.filename):
            filename = secure_filename(f"avatar_{current_user.id}_{file.filename}")
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            current_user.avatar_filename = filename
            
        current_user.bio = bio
        db.session.commit()
        return redirect(url_for("profile", username=current_user.username))
        
    content_html = """
    <div class="p-3 pb-20">
        <form method="post" enctype="multipart/form-data" class="bg-white p-4 border border-gray-300 space-y-4 rounded-sm">
            <div>
                <label class="block text-[11px] font-bold text-gray-500 mb-1 uppercase">Avatar Photo</label>
                <input type="file" name="avatar" accept="image/*" class="w-full text-xs">
            </div>
            <div>
                <label class="block text-[11px] font-bold text-gray-500 mb-1 uppercase">Bio Info</label>
                <textarea name="bio" rows="2" class="w-full p-2 text-xs bg-gray-50 border border-gray-200 rounded-sm focus:outline-none">{{ current_user.bio or '' }}</textarea>
            </div>
            <button class="w-full bg-[#125688] text-white py-1.5 rounded-sm text-xs font-bold uppercase">Save Settings</button>
        </form>
    </div>
    """
    full_html = get_layout(content_html, active_tab='profile', title='Edit Profile')
    return render_template_string(full_html, current_user=current_user)


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        # Auto-migrate: add new columns if they don't exist
        try:
            from sqlalchemy import text, inspect
            inspector = inspect(db.engine)
            existing_cols = [c['name'] for c in inspector.get_columns('user')]
            with db.engine.connect() as conn:
                if 'email' not in existing_cols:
                    conn.execute(text("ALTER TABLE user ADD COLUMN email VARCHAR(150)"))
                    print("✅ Added column: email")
                if 'email_verified' not in existing_cols:
                    conn.execute(text("ALTER TABLE user ADD COLUMN email_verified BOOLEAN DEFAULT 0"))
                    print("✅ Added column: email_verified")
                if 'verify_token' not in existing_cols:
                    conn.execute(text("ALTER TABLE user ADD COLUMN verify_token VARCHAR(64)"))
                    print("✅ Added column: verify_token")
                conn.commit()
        except Exception as e:
            print(f"Migration note: {e}")

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True
    )