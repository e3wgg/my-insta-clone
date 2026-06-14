import os, secrets
from flask import Blueprint, request, redirect, url_for, render_template_string, session
from flask_login import login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime, timezone
from extensions import db
from models import User

auth = Blueprint('auth', __name__)

ALLOWED_EXTENSIONS = {'png','jpg','jpeg','gif','webp','mp4','mov'}

def allowed_file(f):
    return '.' in f and f.rsplit('.',1)[1].lower() in ALLOWED_EXTENSIONS


@auth.route("/welcome")
def welcome():
    if current_user.is_authenticated:
        return redirect(url_for('feed.feed_view'))
    return render_template_string("""
    <!DOCTYPE html><html><head><meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Pacifico&display=swap');
        *{margin:0;padding:0;box-sizing:border-box}
        body{background:#d8dadb;font-family:-apple-system,sans-serif;min-height:100vh;max-width:480px;margin:0 auto;overflow-x:hidden}
        .collage-area{position:relative;width:100%;height:66vh;background:linear-gradient(to bottom,#1a1a1a 0%,#2a2a2a 60%,#d8dadb 100%);overflow:hidden}
        .photo{position:absolute;border:3px solid white;box-shadow:2px 4px 12px rgba(0,0,0,.5);object-fit:cover;background:#555}
        .logo-wrap{position:absolute;left:50%;top:50%;transform:translate(-50%,-50%);text-align:center;z-index:20}
        .insta-cam{width:54px;height:54px;border:3px solid white;border-radius:12px;display:flex;align-items:center;justify-content:center;margin:0 auto 8px;background:rgba(255,255,255,.15)}
        .insta-cam i{font-size:26px;color:white}
        .logo-text{font-family:'Pacifico',cursive;font-size:36px;color:white;text-shadow:0 2px 8px rgba(0,0,0,.6)}
        .buttons-area{padding:24px 28px 30px;background:#d8dadb}
        .btn-row{display:flex;align-items:center;background:#efefef;border:1px solid #c2c2c2;border-radius:4px;padding:13px 16px;margin-bottom:8px;text-decoration:none;color:#333;font-size:14px;font-weight:500}
        .btn-row:hover{background:#e5e5e5}
        .btn-icon{font-size:17px;color:#777;margin-right:12px;width:20px;text-align:center}
        .btn-arrow{font-size:13px;color:#aaa;margin-left:auto}
    </style><title>dewgram</title></head><body>
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
        <div style="position:absolute;inset:0;background:linear-gradient(to bottom,rgba(0,0,0,.35) 0%,rgba(0,0,0,.1) 50%,rgba(216,218,219,.7) 85%,rgba(216,218,219,1) 100%);z-index:10;"></div>
        <div class="logo-wrap">
            <div class="logo-text">Dewgram</div>
        </div>
    </div>
    <div class="buttons-area">
        <a href="/register" class="btn-row"><i class="fa-solid fa-circle-plus btn-icon"></i>Register<i class="fa-solid fa-chevron-right btn-arrow"></i></a>
        <a href="/login" class="btn-row"><i class="fa-regular fa-user btn-icon"></i>Sign In<i class="fa-solid fa-chevron-right btn-arrow"></i></a>
    </div>
    </body></html>""")


@auth.route("/check-username")
def check_username():
    username = request.args.get("username","").strip().lower()
    if not username:
        return {"available": False}
    exists = User.query.filter_by(username=username).first() is not None
    return {"available": not exists}


def _send_otp_email(to_email, username, otp):
    """Send 4-digit OTP via SMTP"""
    try:
        import smtplib
        from email.mime.multipart import MIMEMultipart
        from email.mime.text import MIMEText
        from config import SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, SMTP_FROM

        html = f"""
        <div style="font-family:-apple-system,sans-serif;max-width:420px;margin:0 auto;padding:30px 20px;">
            <div style="text-align:center;margin-bottom:24px;">
                <h1 style="font-size:28px;font-weight:800;color:#4a8db7;margin:0;">Dewgram</h1>
            </div>
            <div style="background:#f9f9f9;border-radius:10px;padding:28px 24px;text-align:center;border:1px solid #e0e0e0;">
                <i style="font-size:36px;">✉️</i>
                <h2 style="font-size:18px;color:#222;margin:14px 0 8px;">Verify Your Email</h2>
                <p style="font-size:14px;color:#666;margin-bottom:24px;">Hi <strong>@{username}</strong>, use this code to verify your account:</p>
                <div style="background:#fff;border:2px solid #4a8db7;border-radius:8px;padding:18px;display:inline-block;margin-bottom:24px;">
                    <span style="font-size:38px;font-weight:800;color:#4a8db7;letter-spacing:12px;">{otp}</span>
                </div>
                <p style="font-size:12px;color:#aaa;">This code expires in <strong>10 minutes</strong>.</p>
                <p style="font-size:12px;color:#aaa;">If you didn't create a Dewgram account, ignore this email.</p>
            </div>
        </div>
        """
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"Your Dewgram verification code: {otp}"
        msg["From"]    = SMTP_FROM
        msg["To"]      = to_email
        msg.attach(MIMEText(html, "html"))

        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT) as server:
            server.login(SMTP_USER, SMTP_PASS)
            server.sendmail(SMTP_FROM, to_email, msg.as_string())
        print(f"✅ OTP sent to {to_email}")
    except Exception as e:
        print(f"❌ Email error: {e}")


@auth.route("/verify-otp", methods=["GET","POST"])
def verify_otp():
    from flask import session as flask_session
    from datetime import datetime, timezone
    uid = flask_session.get('pending_user_id')
    if not uid:
        return redirect(url_for('auth.register'))

    user = User.query.get(uid)
    if not user:
        return redirect(url_for('auth.register'))

    error = None
    if request.method == "POST":
        entered = request.form.get("otp","").strip()
        now = datetime.now(timezone.utc)
        exp = user.otp_expires_at
        if exp and exp.tzinfo is None:
            from datetime import timezone as tz
            exp = exp.replace(tzinfo=tz.utc)

        if not user.email_otp:
            error = "OTP expired. Please register again."
        elif now > exp:
            error = "Code expired. Please register again."
        elif entered != user.email_otp:
            error = "Wrong code. Please try again."
        else:
            user.email_verified = True
            user.email_otp      = None
            user.otp_expires_at = None
            db.session.commit()
            flask_session.pop('pending_user_id', None)
            login_user(user)
            return redirect(url_for('feed.feed_view'))

    return render_template_string("""
    <!DOCTYPE html><html><head><meta charset="UTF-8">
    <meta name="viewport" content="width=device-width,initial-scale=1">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        *{box-sizing:border-box;margin:0;padding:0}
        body{background:#d0d3d6;font-family:-apple-system,sans-serif;display:flex;align-items:center;justify-content:center;min-height:100vh;max-width:480px;margin:0 auto;}
        .card{background:white;border-radius:12px;padding:36px 28px;text-align:center;box-shadow:0 4px 20px rgba(0,0,0,.12);width:100%;max-width:360px;}
        .icon{font-size:48px;margin-bottom:12px}
        h2{font-size:20px;font-weight:800;color:#222;margin-bottom:6px}
        p{font-size:13px;color:#666;margin-bottom:6px}
        .email{font-weight:700;color:#333;font-size:14px;margin-bottom:24px;display:block}
        .otp-inputs{display:flex;gap:10px;justify-content:center;margin-bottom:20px}
        .otp-inputs input{width:56px;height:64px;text-align:center;font-size:28px;font-weight:800;border:2px solid #ddd;border-radius:8px;outline:none;color:#333;background:#fafafa;}
        .otp-inputs input:focus{border-color:#4a8db7;background:#fff}
        .btn{width:100%;padding:14px;background:linear-gradient(to bottom,#7bc96f,#5aab4e);color:white;font-weight:700;font-size:15px;border:none;border-radius:6px;cursor:pointer;margin-bottom:12px}
        .resend{color:#4a8db7;font-size:13px;text-decoration:none;display:block}
        .err{background:#ffe0e0;border:1px solid #f5c0c0;border-radius:6px;padding:10px 14px;font-size:12px;color:#c0392b;margin-bottom:14px}
    </style></head><body>
    <div class="card">
        <div class="icon">✉️</div>
        <h2>Check Your Email</h2>
        <p>We sent a 4-digit code to</p>
        <span class="email">{{ user.email }}</span>
        {% if error %}<div class="err"><i class="fa-solid fa-circle-exclamation" style="margin-right:6px;"></i>{{ error }}</div>{% endif %}
        <form method="post" id="otpForm">
            <div class="otp-inputs">
                <input type="text" maxlength="1" id="o1" name="d1" inputmode="numeric" pattern="[0-9]" autocomplete="off">
                <input type="text" maxlength="1" id="o2" name="d2" inputmode="numeric" pattern="[0-9]" autocomplete="off">
                <input type="text" maxlength="1" id="o3" name="d3" inputmode="numeric" pattern="[0-9]" autocomplete="off">
                <input type="text" maxlength="1" id="o4" name="d4" inputmode="numeric" pattern="[0-9]" autocomplete="off">
            </div>
            <input type="hidden" name="otp" id="hiddenOtp">
            <button type="submit" class="btn">Confirm Code</button>
        </form>
        <a href="/resend-otp" class="resend">Didn't receive it? Resend code</a>
    </div>
    <script>
        const inputs=[document.getElementById('o1'),document.getElementById('o2'),document.getElementById('o3'),document.getElementById('o4')];
        inputs.forEach((inp,i)=>{
            inp.addEventListener('input',function(){
                this.value=this.value.replace(/[^0-9]/g,'');
                if(this.value && i<3) inputs[i+1].focus();
                updateHidden();
            });
            inp.addEventListener('keydown',function(e){
                if(e.key==='Backspace' && !this.value && i>0) inputs[i-1].focus();
            });
        });
        function updateHidden(){
            document.getElementById('hiddenOtp').value=inputs.map(i=>i.value).join('');
        }
        document.getElementById('otpForm').addEventListener('submit',function(){updateHidden();});
        inputs[0].focus();
    </script>
    </body></html>
    """, user=user, error=error)


@auth.route("/resend-otp")
def resend_otp():
    from flask import session as flask_session
    import random
    from datetime import datetime, timezone, timedelta
    uid = flask_session.get('pending_user_id')
    if not uid:
        return redirect(url_for('auth.register'))
    user = User.query.get(uid)
    if not user:
        return redirect(url_for('auth.register'))
    otp = str(random.randint(1000, 9999))
    user.email_otp     = otp
    user.otp_expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)
    db.session.commit()
    _send_otp_email(user.email, user.username, otp)
    return redirect(url_for('auth.verify_otp'))


@auth.route("/register", methods=["GET","POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('feed.feed_view'))
    if request.method == "POST":
        username  = request.form["username"].strip().lower()
        password  = request.form["password"]
        full_name = request.form.get("full_name","").strip()
        email     = request.form.get("email","").strip().lower()

        if not email:
            return redirect(url_for('auth.register'))
        if User.query.filter_by(username=username).first():
            return redirect(url_for('auth.register'))

        import random
        from datetime import datetime, timezone, timedelta
        otp = str(random.randint(1000, 9999))
        expires = datetime.now(timezone.utc) + timedelta(minutes=10)

        token = secrets.token_urlsafe(32)
        user  = User(username=username, password_hash=generate_password_hash(password),
                     verify_token=token, email=email,
                     email_otp=otp, otp_expires_at=expires)
        if full_name: user.bio = full_name
        db.session.add(user)
        db.session.commit()

        # Upload avatar
        file = request.files.get("avatar")
        if file and file.filename:
            from cloudinary_helper import upload_file
            result = upload_file(file, folder="avatars")
            if result:
                user.avatar_url       = result["url"]
                user.avatar_public_id = result["public_id"]
                db.session.commit()

        # Send OTP email
        _send_otp_email(email, username, otp)

        # Store user_id in session for OTP verification
        from flask import session as flask_session
        flask_session['pending_user_id'] = user.id
        return redirect(url_for('auth.verify_otp'))

    return render_template_string("""
    <!DOCTYPE html><html><head><meta charset="UTF-8">
    <meta name="viewport" content="width=device-width,initial-scale=1">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        *{box-sizing:border-box;margin:0;padding:0}
        body{background:#d0d3d6;font-family:-apple-system,sans-serif;max-width:480px;margin:0 auto}
        .login-header{background:linear-gradient(to bottom,#4a8db7,#2a6a96);display:flex;align-items:center;height:48px;padding:0 12px;position:sticky;top:0;z-index:10;box-shadow:0 1px 3px rgba(0,0,0,.2)}
        .field-row{background:#f5f5f5;display:flex;align-items:center;padding:12px 14px}
        .field-divider{height:1px;background:#d0d0d0}
        .field-icon{color:#888;margin-right:10px;font-size:15px;width:18px;text-align:center}
        .field-input{background:transparent;border:none;outline:none;font-size:14px;color:#333;width:100%}
        .field-input::placeholder{color:#aaa}
        .register-btn{background:linear-gradient(to bottom,#7bc96f,#5aab4e);border:1px solid #4a9140;color:white;font-weight:700;font-size:15px;padding:14px;border-radius:3px;width:100%;cursor:pointer}
        .photo-box{width:72px;height:72px;border:2px dashed #aaa;border-radius:4px;display:flex;flex-direction:column;align-items:center;justify-content:center;background:#e8e8e8;cursor:pointer;flex-shrink:0}
        .photo-box i{font-size:26px;color:#999}
        .photo-box span{font-size:9px;color:#999;font-weight:700;margin-top:3px}
        .green-dot{width:10px;height:10px;border-radius:50%;display:inline-block;margin-left:2px}
        .section-label{font-size:11px;font-weight:700;color:#666;text-transform:uppercase;letter-spacing:.05em;margin:14px 0 6px 2px}
    </style><title>Register</title></head><body>
    <div class="login-header">
        <a href="/welcome" style="color:white;font-size:18px;margin-right:12px;text-decoration:none;"><i class="fa-solid fa-chevron-left"></i></a>
        <span style="color:white;font-weight:700;font-size:15px;letter-spacing:.04em;text-transform:uppercase;">Register</span>
    </div>
    <div style="padding:12px 12px 30px">
        <div style="background:#f5f5f5;border:1px solid #d0d0d0;border-radius:4px;display:flex;overflow:hidden;margin-bottom:12px;">
            <div style="width:88px;border-right:1px solid #d0d0d0;display:flex;align-items:center;justify-content:center;background:#eaeaea;">
                <label for="avatar_upload" class="photo-box" id="photo_label">
                    <img id="avatar_preview" src="" style="display:none;width:100%;height:100%;object-fit:cover;border-radius:4px;position:absolute;top:0;left:0;">
                    <i class="fa-regular fa-user" id="avatar_icon"></i>
                    <span id="avatar_txt">PHOTO</span>
                    <input type="file" id="avatar_upload" name="avatar" accept="image/*" style="display:none"
                           onchange="
                               var f=this.files[0];
                               if(f){
                                   var r=new FileReader();
                                   r.onload=function(e){
                                       document.getElementById('avatar_preview').src=e.target.result;
                                       document.getElementById('avatar_preview').style.display='block';
                                       document.getElementById('avatar_icon').style.display='none';
                                       document.getElementById('avatar_txt').style.display='none';
                                       document.getElementById('photo_label').style.position='relative';
                                       document.getElementById('photo_label').style.overflow='hidden';
                                   };
                                   r.readAsDataURL(f);
                               }">
                </label>
            </div>
            <div style="flex:1;">
                <div class="field-row">
                    <i class="fa-regular fa-user field-icon"></i>
                    <input name="username" id="username" placeholder="Username" autocomplete="off" required class="field-input">
                    <span class="green-dot" id="udot" style="display:none;background:#aaa;"></span>
                </div>
                <div class="field-divider"></div>
                <div class="field-row">
                    <i class="fa-solid fa-lock field-icon"></i>
                    <input type="password" id="pw" placeholder="Password" required class="field-input">
                </div>
            </div>
        </div>
        <div class="section-label">Profile</div>
        <div style="background:#f5f5f5;border:1px solid #d0d0d0;border-radius:4px;overflow:hidden;margin-bottom:10px;">
            <div class="field-row" style="border-bottom:1px solid #d0d0d0;">
                <i class="fa-regular fa-id-badge field-icon"></i>
                <input id="fname" placeholder="Name" class="field-input">
            </div>
            <div class="field-row">
                <i class="fa-regular fa-envelope field-icon"></i>
                <input id="email" type="email" placeholder="Email" class="field-input">
            </div>
        </div>
        <p style="font-size:11px;color:#666;margin-bottom:6px;">Your email address will always remain private.</p>
        <p style="font-size:11px;color:#666;margin-bottom:12px;">By clicking Register you agree to the <a href="#" style="color:#3897f0;">Terms of Service</a> and <a href="#" style="color:#3897f0;">Privacy Policy</a>.</p>
        <form method="post" id="reg_form" enctype="multipart/form-data">
            <input type="hidden" name="username" id="h_user">
            <input type="hidden" name="password" id="h_pw">
            <input type="hidden" name="full_name" id="h_fn">
            <input type="hidden" name="email" id="h_em">
            <div id="err_box" style="display:none;background:#ffe0e0;border:1px solid #f5c0c0;border-radius:4px;padding:8px 12px;font-size:12px;color:#c0392b;margin-bottom:8px;">
                <i class="fa-solid fa-circle-exclamation" style="margin-right:6px;"></i>This username is not available.
            </div>
            <button type="submit" class="register-btn">Register</button>
        </form>
    </div>
    <script>
        let ok=false,t=null;
        const inp=document.getElementById('username'),dot=document.getElementById('udot'),err=document.getElementById('err_box');
        inp.addEventListener('input',function(){
            clearTimeout(t);const v=this.value.trim();
            if(!v){dot.style.display='none';err.style.display='none';return;}
            dot.style.background='#aaa';dot.style.display='inline-block';
            t=setTimeout(()=>{
                fetch('/check-username?username='+encodeURIComponent(v)).then(r=>r.json()).then(d=>{
                    ok=d.available;dot.style.background=ok?'#7dc832':'#e74c3c';
                    err.style.display=ok?'none':'block';
                });
            },400);
        });
        document.getElementById('reg_form').addEventListener('submit',function(e){
            if(!ok&&inp.value.trim()){e.preventDefault();err.style.display='block';return;}
            document.getElementById('h_user').value=inp.value.trim();
            document.getElementById('h_pw').value=document.getElementById('pw').value;
            document.getElementById('h_fn').value=document.getElementById('fname').value;
            document.getElementById('h_em').value=document.getElementById('email').value;
        });
    </script>
    </body></html>""")


@auth.route("/login", methods=["GET","POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('feed.feed_view'))
    error = None
    if request.args.get('banned'):
        error = "banned"
    if request.method == "POST":
        username = request.form["username"].strip().lower()
        password = request.form["password"]
        try:
            user = User.query.filter_by(username=username).first()
            if not user or not check_password_hash(user.password_hash, password):
                error = "Incorrect username or password."
            elif user.is_banned:
                error = "banned"
            else:
                login_user(user)
                return redirect(url_for('feed.feed_view'))
        except Exception:
            try:
                from sqlalchemy import text, inspect
                inspector = inspect(db.engine)
                cols = [c['name'] for c in inspector.get_columns('user')]
                with db.engine.connect() as conn:
                    for col,typ in [('email','VARCHAR(150)'),('email_verified','BOOLEAN DEFAULT 0'),
                                    ('verify_token','VARCHAR(64)'),('is_banned','BOOLEAN DEFAULT 0'),
                                    ('is_admin','BOOLEAN DEFAULT 0')]:
                        if col not in cols:
                            conn.execute(text(f"ALTER TABLE user ADD COLUMN {col} {typ}"))
                    conn.commit()
                user = User.query.filter_by(username=username).first()
                if user and check_password_hash(user.password_hash, password):
                    login_user(user); return redirect(url_for('feed.feed_view'))
                else:
                    error = "Incorrect username or password."
            except Exception as e2:
                error = str(e2)

    return render_template_string("""
    <!DOCTYPE html><html><head><meta charset="UTF-8">
    <meta name="viewport" content="width=device-width,initial-scale=1">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        *{box-sizing:border-box;margin:0;padding:0}
        body{background:#d0d3d6;font-family:-apple-system,sans-serif;max-width:480px;margin:0 auto}
        .login-header{background:linear-gradient(to bottom,#4a8db7,#2a6a96);display:flex;align-items:center;height:48px;padding:0 12px;position:sticky;top:0;z-index:10}
        .field-card{background:#f0f0f0;border:1px solid #c8c8c8;border-radius:3px;overflow:hidden}
        .field-row{display:flex;align-items:center;padding:14px;background:#f0f0f0}
        .field-divider{height:1px;background:#c8c8c8}
        .field-icon{color:#888;margin-right:10px;font-size:15px;width:18px;text-align:center;flex-shrink:0}
        .field-input{background:transparent;border:none;outline:none;font-size:14px;color:#333;width:100%}
        .field-input::placeholder{color:#999}
        .signin-btn{background:linear-gradient(to bottom,#7bc96f,#5aab4e);border:1px solid #4a9140;color:white;font-weight:700;font-size:15px;padding:14px;border-radius:3px;width:100%;cursor:pointer}
        .insta-cam{width:52px;height:52px;border:2px solid #aaa;border-radius:10px;display:flex;align-items:center;justify-content:center;background:#e0e0e0;margin:0 auto 18px}
    </style><title>Sign In</title></head><body>
    <div class="login-header">
        <a href="/welcome" style="color:white;font-size:18px;margin-right:12px;text-decoration:none;"><i class="fa-solid fa-chevron-left"></i></a>
        <span style="color:white;font-weight:700;font-size:15px;text-transform:uppercase;letter-spacing:.04em;">Sign In</span>
    </div>
    <div style="padding:28px 16px 20px">
        <div style="text-align:center;margin:0 auto 18px;">
            <div style="display:inline-flex;align-items:center;justify-content:center;width:60px;height:60px;border-radius:16px;background:linear-gradient(135deg,#4a8db7,#2a6a96);box-shadow:0 4px 14px rgba(42,106,150,.4);">
                <svg viewBox="0 0 40 40" width="34" height="34" xmlns="http://www.w3.org/2000/svg">
                  <!-- D letter stylized -->
                  <path d="M8 8 L8 32 L18 32 Q30 32 30 20 Q30 8 18 8 Z" fill="none" stroke="white" stroke-width="3" stroke-linejoin="round"/>
                  <path d="M8 20 L22 20" stroke="white" stroke-width="2.5" stroke-linecap="round"/>
                  <!-- dot -->
                  <circle cx="32" cy="10" r="2.5" fill="white"/>
                </svg>
            </div>
        </div>
        <form method="post" style="margin-bottom:14px">
            <div class="field-card">
                <div class="field-row"><i class="fa-regular fa-user field-icon"></i><input name="username" placeholder="Username or Email" autocomplete="off" required class="field-input"></div>
                <div class="field-divider"></div>
                <div class="field-row"><i class="fa-solid fa-lock field-icon"></i><input type="password" name="password" placeholder="Password" required class="field-input"></div>
            </div>
            {% if error == 'banned' %}
            <div style="margin-top:10px;background:#fff0f0;border:1px solid #f5c0c0;border-radius:4px;padding:12px;font-size:12px;color:#c0392b;text-align:center;">
                <i class="fa-solid fa-ban" style="font-size:20px;display:block;margin-bottom:6px;"></i>
                <strong>Your account has been suspended.</strong><br>
                <span style="color:#888;font-size:11px;">Contact support if this is a mistake.</span><br>
                <a href="/support" style="display:inline-block;margin-top:8px;background:#4a8db7;color:white;padding:6px 18px;border-radius:4px;font-size:12px;font-weight:700;text-decoration:none;">Contact Support</a>
            </div>
            {% elif error %}
            <div style="margin-top:10px;background:#ffe0e0;border:1px solid #f5c0c0;border-radius:4px;padding:9px 12px;font-size:12px;color:#c0392b;">
                <i class="fa-solid fa-circle-exclamation" style="margin-right:6px;"></i>{{ error }}
            </div>
            {% endif %}
            <div style="margin-top:10px"><button type="submit" class="signin-btn">Sign In</button></div>
        </form>
        <div style="text-align:center;margin-top:18px;"><a href="/change-password" style="color:#3a7bbf;font-size:14px;text-decoration:none;">Forgot Password?</a></div>
    </div>
    </body></html>""", error=error)


@auth.route("/change-password", methods=["GET","POST"])
def change_password():
    msg   = None
    error = None
    if request.method == "POST":
        username    = request.form.get("username","").strip().lower()
        old_pw      = request.form.get("old_password","").strip()
        new_pw      = request.form.get("new_password","").strip()
        confirm_pw  = request.form.get("confirm_password","").strip()

        if not username or not old_pw or not new_pw or not confirm_pw:
            error = "Please fill in all fields."
        elif new_pw != confirm_pw:
            error = "New passwords don't match."
        elif len(new_pw) < 6:
            error = "New password must be at least 6 characters."
        else:
            user = User.query.filter_by(username=username).first()
            if not user or not check_password_hash(user.password_hash, old_pw):
                error = "Username or current password is incorrect."
            else:
                user.password_hash = generate_password_hash(new_pw)
                db.session.commit()
                msg = "✅ Password changed successfully! You can now sign in."

    return render_template_string("""
    <!DOCTYPE html><html><head><meta charset="UTF-8">
    <meta name="viewport" content="width=device-width,initial-scale=1">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        *{box-sizing:border-box;margin:0;padding:0}
        body{background:#d0d3d6;font-family:-apple-system,sans-serif;max-width:480px;margin:0 auto;min-height:100vh}
        .hdr{background:linear-gradient(to bottom,#4a8db7,#2a6a96);display:flex;align-items:center;height:48px;padding:0 14px;position:sticky;top:0}
        .hdr a{color:white;font-size:17px;margin-right:12px;text-decoration:none}
        .hdr span{color:white;font-weight:700;font-size:15px;text-transform:uppercase;letter-spacing:.04em}
        .card{background:#f5f5f5;border:1px solid #d0d0d0;border-radius:4px;overflow:hidden;margin:16px 14px}
        .field-row{display:flex;align-items:center;padding:13px 14px;background:#f5f5f5;border-bottom:1px solid #d0d0d0}
        .field-row:last-child{border-bottom:none}
        .fi{color:#888;margin-right:10px;font-size:14px;width:18px;text-align:center;flex-shrink:0}
        .fi-input{background:transparent;border:none;outline:none;font-size:14px;color:#333;width:100%}
        .fi-input::placeholder{color:#aaa}
        .save-btn{display:block;width:calc(100% - 28px);margin:0 14px 16px;padding:13px;background:linear-gradient(to bottom,#7bc96f,#5aab4e);color:white;font-weight:700;font-size:14px;border:none;border-radius:4px;cursor:pointer}
        .msg-ok{background:#e8fdf0;border:1px solid #b2dfdb;border-radius:4px;padding:12px 14px;margin:0 14px 14px;font-size:13px;color:#27ae60;text-align:center}
        .msg-err{background:#ffe0e0;border:1px solid #f5c0c0;border-radius:4px;padding:12px 14px;margin:0 14px 14px;font-size:13px;color:#c0392b}
        .section-lbl{font-size:11px;font-weight:700;color:#666;text-transform:uppercase;letter-spacing:.05em;padding:14px 16px 6px}
        .signin-link{text-align:center;padding:10px;font-size:13px;color:#4a8db7;text-decoration:none;display:block}
    </style></head><body>
    <div class="hdr">
        <a href="javascript:history.back()"><i class="fa-solid fa-chevron-left"></i></a>
        <span>Change Password</span>
    </div>

    {% if msg %}
        <div class="msg-ok">{{ msg }}</div>
        <a href="/login" class="signin-link">← Sign In</a>
    {% else %}
        {% if error %}<div class="msg-err"><i class="fa-solid fa-circle-exclamation" style="margin-right:6px;"></i>{{ error }}</div>{% endif %}
        <form method="post">
            <div class="section-lbl">Your Account</div>
            <div class="card">
                <div class="field-row">
                    <i class="fa-regular fa-user fi"></i>
                    <input name="username" placeholder="Username" autocomplete="off" required class="fi-input">
                </div>
            </div>
            <div class="section-lbl">Passwords</div>
            <div class="card">
                <div class="field-row">
                    <i class="fa-solid fa-lock fi"></i>
                    <input type="password" name="old_password" placeholder="Current password" required class="fi-input">
                </div>
                <div class="field-row">
                    <i class="fa-solid fa-key fi"></i>
                    <input type="password" name="new_password" placeholder="New password" required class="fi-input">
                </div>
                <div class="field-row">
                    <i class="fa-solid fa-check fi"></i>
                    <input type="password" name="confirm_password" placeholder="Confirm new password" required class="fi-input">
                </div>
            </div>
            <button type="submit" class="save-btn">Change Password</button>
        </form>
    {% endif %}
    </body></html>
    """, msg=msg, error=error, current_user=current_user)


@auth.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for('auth.welcome'))


@auth.route("/verify-email/<token>")
def verify_email(token):
    user = User.query.filter_by(verify_token=token).first()
    if user:
        user.email_verified = True; user.verify_token = None
        db.session.commit(); success = True
    else:
        success = False
    return render_template_string("""
    <!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>body{background:#d0d3d6;display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0;font-family:-apple-system,sans-serif}</style>
    </head><body>
    <div style="background:white;border-radius:8px;padding:32px 24px;text-align:center;max-width:320px;box-shadow:0 2px 12px rgba(0,0,0,.1);">
        {% if success %}<i class="fa-solid fa-circle-check" style="font-size:48px;color:#4caf50;margin-bottom:12px;"></i>
        <h2 style="font-size:16px;font-weight:700;color:#222;margin-bottom:8px;">Account Verified!</h2>
        <a href="/" style="background:linear-gradient(to bottom,#4a8db7,#2a6a96);color:white;padding:10px 24px;border-radius:4px;font-size:13px;font-weight:700;text-decoration:none;">Go to Feed</a>
        {% else %}<i class="fa-solid fa-circle-xmark" style="font-size:48px;color:#e74c3c;margin-bottom:12px;"></i>
        <h2 style="font-size:16px;font-weight:700;color:#222;">Invalid Link</h2>{% endif %}
    </div></body></html>""", success=success)


@auth.route("/verify-pending")
@login_required
def verify_pending():
    return render_template_string("""
    <!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>body{background:#d0d3d6;display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0;font-family:-apple-system,sans-serif}</style>
    </head><body>
    <div style="background:white;border-radius:8px;padding:32px 24px;text-align:center;max-width:320px;box-shadow:0 2px 12px rgba(0,0,0,.1);">
        <i class="fa-regular fa-envelope" style="font-size:48px;color:#4a8db7;margin-bottom:12px;"></i>
        <h2 style="font-size:16px;font-weight:700;color:#222;margin-bottom:8px;">Verify Your Email</h2>
        <p style="font-size:12px;color:#666;margin-bottom:6px;">We sent a link to:</p>
        <p style="font-size:13px;font-weight:700;color:#333;margin-bottom:16px;">{{ current_user.email }}</p>
        <a href="/" style="background:linear-gradient(to bottom,#4a8db7,#2a6a96);color:white;padding:10px 24px;border-radius:4px;font-size:13px;font-weight:700;text-decoration:none;">Continue to Feed</a>
    </div></body></html>""", current_user=current_user)


@auth.route("/settings")
@login_required
def settings():
    return render_template_string("""
    <!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        *{box-sizing:border-box;margin:0;padding:0}body{background:#d8dadb;font-family:-apple-system,sans-serif;max-width:480px;margin:0 auto}
        .hdr{background:linear-gradient(to bottom,#4a8db7,#2a6a96);display:flex;align-items:center;height:48px;padding:0 14px;position:sticky;top:0;z-index:10}
        .row{display:flex;align-items:center;justify-content:space-between;background:#f5f5f5;border-bottom:1px solid #ddd;padding:14px 16px;text-decoration:none;color:#333}
        .row:last-child{border-bottom:none}
        .rl{display:flex;align-items:center;gap:12px;font-size:13px}
        .ri{width:20px;text-align:center;color:#777;font-size:15px}
        .sec{font-size:11px;font-weight:700;color:#888;text-transform:uppercase;letter-spacing:.05em;padding:14px 2px 6px}
    </style></head><body>
    <div class="hdr">
        <a href="javascript:history.back()" style="color:white;font-size:18px;margin-right:14px;text-decoration:none;"><i class="fa-solid fa-chevron-left"></i></a>
        <span style="color:white;font-weight:700;font-size:15px;text-transform:uppercase;letter-spacing:.04em;">Settings</span>
    </div>
    <div style="padding:12px 14px 40px">
        <div class="sec">Account</div>
        <div style="border:1px solid #d0d0d0;border-radius:4px;overflow:hidden;margin-bottom:14px">
            <a href="/edit-profile" class="row"><div class="rl"><i class="fa-regular fa-user ri"></i>Edit Profile</div><i class="fa-solid fa-chevron-right" style="color:#bbb;font-size:12px"></i></a>
            <a href="/change-password" class="row"><div class="rl"><i class="fa-solid fa-lock ri"></i>Change Password</div><i class="fa-solid fa-chevron-right" style="color:#bbb;font-size:12px"></i></a>
            <a href="/privacy" class="row"><div class="rl"><i class="fa-solid fa-shield-halved ri"></i>Privacy</div><i class="fa-solid fa-chevron-right" style="color:#bbb;font-size:12px"></i></a>
            {% if current_user.email %}
            <div class="row" style="cursor:default">
                <div class="rl"><i class="fa-regular fa-envelope ri"></i><span>{{ current_user.email }}</span></div>
                {% if current_user.email_verified %}<span style="font-size:11px;color:#4caf50;font-weight:700;"><i class="fa-solid fa-circle-check"></i> Verified</span>
                {% else %}<span style="font-size:11px;color:#e67e22;font-weight:700;">Pending</span>{% endif %}
            </div>{% endif %}
        </div>
        <div class="sec">Support</div>
        <div style="border:1px solid #d0d0d0;border-radius:4px;overflow:hidden;margin-bottom:14px">
            <a href="/support" class="row"><div class="rl"><i class="fa-regular fa-circle-question ri"></i>Help & Support</div><i class="fa-solid fa-chevron-right" style="color:#bbb;font-size:12px"></i></a>
        </div>
        <div style="border:1px solid #f5c0c0;border-radius:4px;overflow:hidden">
            <a href="/logout" class="row" style="color:#e74c3c"><div class="rl" style="color:#e74c3c"><i class="fa-solid fa-right-from-bracket ri" style="color:#e74c3c"></i>Log Out</div></a>
        </div>
    </div></body></html>""", current_user=current_user)


@auth.route("/privacy", methods=["GET","POST"])
@login_required
def privacy():
    if request.method == "POST":
        current_user.is_private   = 'is_private'   in request.form
        current_user.saves_public = 'saves_private' not in request.form
        db.session.commit()
    return render_template_string("""
    <!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        *{box-sizing:border-box;margin:0;padding:0}body{background:#d8dadb;font-family:-apple-system,sans-serif;max-width:480px;margin:0 auto}
        .hdr{background:linear-gradient(to bottom,#4a8db7,#2a6a96);display:flex;align-items:center;height:48px;padding:0 14px;position:sticky;top:0}
        .hdr a{color:white;font-size:17px;margin-right:14px;text-decoration:none}
        .hdr span{color:white;font-weight:700;font-size:15px;text-transform:uppercase}
        .card{background:white;border:1px solid #d0d0d0;border-radius:6px;margin:14px;overflow:hidden}
        .prow{display:flex;align-items:center;justify-content:space-between;padding:16px;border-bottom:1px solid #f0f0f0}
        .prow:last-child{border-bottom:none}
        .ptitle{font-size:14px;font-weight:600;color:#222;margin-bottom:2px}
        .pdesc{font-size:11px;color:#888;line-height:1.4}
        .toggle{position:relative;width:46px;height:26px;flex-shrink:0;margin-left:12px}
        .toggle input{opacity:0;width:0;height:0}
        .slider{position:absolute;inset:0;background:#ccc;border-radius:26px;cursor:pointer;transition:.3s}
        .slider:before{content:"";position:absolute;height:20px;width:20px;left:3px;bottom:3px;background:white;border-radius:50%;transition:.3s}
        input:checked+.slider{background:#4a8db7}
        input:checked+.slider:before{transform:translateX(20px)}
        .saved-banner{background:#e8f4fd;border:1px solid #b3d9f7;border-radius:6px;padding:10px 14px;margin:14px 14px 0;font-size:12px;color:#1a6a9a;{% if request.method != 'POST' %}display:none;{% endif %}}
    </style></head><body>
    <div class="hdr">
        <a href="/settings"><i class="fa-solid fa-chevron-left"></i></a>
        <span>Privacy</span>
    </div>
    <div class="saved-banner"><i class="fa-solid fa-circle-check" style="margin-right:6px;"></i>Settings saved!</div>
    <form method="post">
        <div style="padding:14px 14px 0;font-size:11px;font-weight:700;color:#888;text-transform:uppercase;letter-spacing:.05em;">Account</div>
        <div class="card">
            <div class="prow">
                <div><div class="ptitle"><i class="fa-solid fa-lock" style="color:#4a8db7;margin-right:6px;font-size:13px;"></i>Private Account</div>
                <div class="pdesc">Only your followers can see your posts, following list, and saved posts.</div></div>
                <label class="toggle"><input type="checkbox" name="is_private" {% if current_user.is_private %}checked{% endif %} onchange="this.form.submit()"><span class="slider"></span></label>
            </div>
        </div>
        <div style="padding:0 14px;font-size:11px;font-weight:700;color:#888;text-transform:uppercase;letter-spacing:.05em;">Saved Posts</div>
        <div class="card">
            <div class="prow">
                <div><div class="ptitle"><i class="fa-regular fa-bookmark" style="color:#4a8db7;margin-right:6px;font-size:13px;"></i>Private Saved Posts</div>
                <div class="pdesc">When ON, only you can see your saved posts tab.</div></div>
                <label class="toggle"><input type="checkbox" name="saves_private" {% if not current_user.saves_public %}checked{% endif %} onchange="this.form.submit()"><span class="slider"></span></label>
            </div>
        </div>
    </form>
    </body></html>""", current_user=current_user, request=request)
