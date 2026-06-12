import os, time
from functools import wraps
from flask import Blueprint, request, redirect, url_for, render_template_string, session, jsonify
from werkzeug.security import generate_password_hash
from extensions import db
from models import User, Post, Report, SupportTicket, SupportMessage
from config import (ADMIN_SECRET_PATH, ADMIN_PASSWORD, ADMIN_IP_WHITELIST,
                    MAX_ATTEMPTS, LOCKOUT_SECS)

admin_bp = Blueprint('admin', __name__)
_brute_store: dict = {}

def _get_ip():
    return request.headers.get("X-Forwarded-For", request.remote_addr or "").split(",")[0].strip()

def _is_locked(ip):
    rec = _brute_store.get(ip)
    return bool(rec and rec["until"] > time.time())

def _record_fail(ip):
    rec = _brute_store.setdefault(ip, {"count":0,"until":0})
    rec["count"] += 1
    if rec["count"] >= MAX_ATTEMPTS:
        rec["until"] = time.time() + LOCKOUT_SECS
        rec["count"] = 0

def _reset_fail(ip): _brute_store.pop(ip, None)

def admin_required(f):
    @wraps(f)
    def decorated(*args,**kwargs):
        ip = _get_ip()
        if ADMIN_IP_WHITELIST and ip not in ADMIN_IP_WHITELIST:
            return "404 Not Found", 404
        if not session.get("admin_authed"):
            return redirect(f"/{ADMIN_SECRET_PATH}/login")
        return f(*args,**kwargs)
    return decorated

from flask import current_app

@admin_bp.route(f"/{ADMIN_SECRET_PATH}/login", methods=["GET", "POST"])
def admin_login():
    import time
    ip = _get_ip()

    # IP whitelist
    if ADMIN_IP_WHITELIST and ip not in ADMIN_IP_WHITELIST:
        return "404 Not Found", 404          # يبدو كأنه غير موجود

    error = None
    lockout_left = 0

    if _is_locked(ip):
        rec = _brute_store.get(ip, {})
        lockout_left = max(0, int(rec.get("until", 0) - time.time()))
        error = f"Too many attempts. Try again in {lockout_left}s."

    elif request.method == "POST":
        pw = request.form.get("password", "")
        if pw == ADMIN_PASSWORD:
            _reset_fail(ip)
            session["admin_authed"] = True
            session.permanent = False
            return redirect(f"/{ADMIN_SECRET_PATH}/")
        else:
            _record_fail(ip)
            rem = MAX_ATTEMPTS - _brute_store.get(ip, {}).get("count", 0)
            error = f"Wrong password. {max(rem,0)} attempt(s) left."

    return render_template_string("""
    <!DOCTYPE html><html><head><meta charset="UTF-8">
    <meta name="viewport" content="width=device-width,initial-scale=1">
    <title>404 Not Found</title>
    <style>
        *{box-sizing:border-box;margin:0;padding:0}
        body{background:#0d0d0d;display:flex;align-items:center;justify-content:center;min-height:100vh;font-family:-apple-system,sans-serif}
        .card{background:#111;border:1px solid #222;border-radius:14px;padding:44px 32px;width:340px;text-align:center;box-shadow:0 12px 40px rgba(0,0,0,0.6)}
        .icon{font-size:40px;margin-bottom:10px}
        h2{color:#e94560;font-size:17px;margin-bottom:4px;letter-spacing:.02em}
        .sub{color:#555;font-size:12px;margin-bottom:28px}
        input{width:100%;padding:13px 14px;border-radius:7px;border:1px solid #222;background:#0d0d0d;color:#eee;font-size:14px;margin-bottom:10px;outline:none;transition:.2s}
        input:focus{border-color:#e94560;background:#151515}
        button{width:100%;padding:13px;background:#e94560;color:#fff;border:none;border-radius:7px;font-size:14px;font-weight:700;cursor:pointer;letter-spacing:.03em;transition:.2s}
        button:hover{background:#c73652}
        button:disabled{background:#444;cursor:not-allowed}
        .err{background:#1a000a;border:1px solid #5a0020;color:#ff6b8a;padding:10px 14px;border-radius:7px;font-size:12px;margin-bottom:14px;text-align:left}
        .dots{letter-spacing:4px;color:#333;font-size:22px;margin-bottom:18px}
    </style></head><body>
    <div class="card">
        <div class="icon">🔒</div>
        <h2>Restricted Area</h2>
        <div class="sub">Unauthorized access is logged and reported.</div>
        {% if error %}<div class="err">⚠ {{ error }}</div>{% endif %}
        <form method="post">
            <input type="password" name="password" placeholder="••••••••••••" autofocus
                   {% if lockout_left > 0 %}disabled{% endif %}>
            <button type="submit" {% if lockout_left > 0 %}disabled{% endif %}>
                {% if lockout_left > 0 %}Locked ({{ lockout_left }}s){% else %}Enter{% endif %}
            </button>
        </form>
        <div class="dots" style="margin-top:22px">• • •</div>
    </div>
    {% if lockout_left > 0 %}
    <script>
        let s = {{ lockout_left }};
        const btn = document.querySelector('button');
        const inp = document.querySelector('input');
        const t = setInterval(()=>{
            s--;
            btn.textContent = s > 0 ? `Locked (${s}s)` : 'Enter';
            if(s <= 0){ btn.disabled=false; inp.disabled=false; clearInterval(t); }
        },1000);
    </script>
    {% endif %}
    </body></html>
    """, error=error, lockout_left=lockout_left)


@admin_bp.route(f"/{ADMIN_SECRET_PATH}/logout")
def admin_logout():
    session.pop("admin_authed", None)
    return redirect(f"/{ADMIN_SECRET_PATH}/login")


@admin_bp.route(f"/{ADMIN_SECRET_PATH}/")
@admin_required
def admin_dashboard():
    search  = request.args.get('q', '').strip()
    ffilter = request.args.get('filter', 'all')  # all / banned / active

    query = User.query
    if search:
        query = query.filter(User.username.ilike(f'%{search}%'))
    if ffilter == 'banned':
        query = query.filter_by(is_banned=True)
    elif ffilter == 'active':
        query = query.filter_by(is_banned=False)
    users = query.order_by(User.created_at.desc()).all()

    total_users  = User.query.count()
    total_posts  = Post.query.count()
    banned_count = User.query.filter_by(is_banned=True).count()
    reports_count = Report.query.filter_by(status='pending').count()

    return render_template_string("""
    <!DOCTYPE html><html><head><meta charset="UTF-8">
    <meta name="viewport" content="width=device-width,initial-scale=1">
    <title>Admin — Dewgram</title>
    <style>
        *{box-sizing:border-box;margin:0;padding:0}
        body{background:#f0f2f5;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;color:#333}
        .topbar{background:linear-gradient(135deg,#0d0d0d,#1a1a2e);padding:0 24px;height:56px;display:flex;align-items:center;justify-content:space-between;position:sticky;top:0;z-index:100;box-shadow:0 2px 8px rgba(0,0,0,.4)}
        .topbar h1{color:#fff;font-size:17px;font-weight:700}
        .topbar a{color:#aaa;font-size:12px;text-decoration:none;padding:6px 14px;border:1px solid #333;border-radius:4px;white-space:nowrap}
        .topbar a:hover{color:#fff;border-color:#e94560}
        .toplinks{display:flex;gap:8px;align-items:center}
        .stats{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;padding:18px 24px 0}
        .stat{background:#fff;border-radius:10px;padding:16px;text-align:center;box-shadow:0 1px 4px rgba(0,0,0,.08)}
        .stat-num{font-size:28px;font-weight:800;color:#1a1a2e}
        .stat-lbl{font-size:10px;color:#999;margin-top:3px;text-transform:uppercase;letter-spacing:.05em}
        .stat.red .stat-num{color:#e94560}
        .stat.orange .stat-num{color:#e67e22}
        .section{padding:18px 24px}
        .section-title{font-size:12px;font-weight:700;color:#999;text-transform:uppercase;letter-spacing:.05em;margin-bottom:10px}
        .filters{display:flex;gap:8px;margin-bottom:12px;flex-wrap:wrap;}
        .filter-btn{padding:6px 14px;border-radius:20px;font-size:12px;font-weight:700;text-decoration:none;border:1px solid #ddd;background:#fff;color:#555}
        .filter-btn.active{background:#1a1a2e;color:#fff;border-color:#1a1a2e}
        .search-bar{display:flex;gap:8px;margin-bottom:14px}
        .search-bar input{flex:1;padding:10px 14px;border:1px solid #ddd;border-radius:6px;font-size:13px;outline:none}
        .search-bar button{padding:10px 18px;background:#4a8db7;color:#fff;border:none;border-radius:6px;font-size:13px;font-weight:700;cursor:pointer}
        table{width:100%;background:#fff;border-radius:10px;box-shadow:0 1px 4px rgba(0,0,0,.07);border-collapse:collapse;overflow:hidden}
        th{background:#f8f9fa;padding:11px 14px;text-align:left;font-size:10px;font-weight:700;color:#999;text-transform:uppercase;letter-spacing:.05em;border-bottom:1px solid #eee}
        td{padding:11px 14px;font-size:13px;border-bottom:1px solid #f5f5f5;vertical-align:middle}
        tr:last-child td{border-bottom:none}
        tr:hover td{background:#fafafa}
        .av{width:34px;height:34px;border-radius:50%;object-fit:cover;border:1px solid #ddd}
        .avp{width:34px;height:34px;border-radius:50%;background:#dde;display:inline-flex;align-items:center;justify-content:center;font-size:11px;font-weight:700;color:#556}
        .badge{padding:2px 8px;border-radius:20px;font-size:10px;font-weight:700}
        .b-ban{background:#fff0f0;color:#e94560;border:1px solid #ffc0c0}
        .b-ok{background:#f0fff4;color:#27ae60;border:1px solid #b2dfdb}
        .b-admin{background:#fff8e1;color:#f39c12;border:1px solid #ffe082;margin-left:3px}
        .btn{display:inline-block;padding:5px 10px;border-radius:4px;font-size:11px;font-weight:700;text-decoration:none;cursor:pointer;border:none;margin:1px;white-space:nowrap}
        .br{background:#e94560;color:#fff}.bo{background:#e67e22;color:#fff}.bg{background:#27ae60;color:#fff}.bb{background:#4a8db7;color:#fff}.bx{background:#95a5a6;color:#fff}
        .overlay{display:none;position:fixed;inset:0;background:rgba(0,0,0,.55);z-index:200;align-items:center;justify-content:center}
        .overlay.on{display:flex}
        .modal{background:#fff;border-radius:12px;padding:28px 24px;width:360px;box-shadow:0 8px 32px rgba(0,0,0,.2)}
        .modal h3{font-size:15px;font-weight:700;margin-bottom:6px}
        .modal p{font-size:12px;color:#777;margin-bottom:18px}
        .modal input{width:100%;padding:10px;border:1px solid #ddd;border-radius:6px;font-size:13px;margin-bottom:12px;outline:none}
        .mbtns{display:flex;gap:8px}
        .mbtns button{flex:1;padding:10px;border:none;border-radius:6px;font-size:13px;font-weight:700;cursor:pointer}
        .mc{background:#e94560;color:#fff}.mk{background:#eee;color:#555}
        .pgrid{display:grid;grid-template-columns:repeat(auto-fill,minmax(90px,1fr));gap:6px;margin-top:10px;max-height:320px;overflow-y:auto}
        .pt{position:relative;aspect-ratio:1;border-radius:6px;overflow:hidden;background:#ddd}
        .pt img,.pt video{width:100%;height:100%;object-fit:cover}
        .pt .dx{position:absolute;top:3px;right:3px;background:rgba(233,69,96,.9);color:#fff;border:none;border-radius:3px;padding:2px 5px;font-size:9px;font-weight:700;cursor:pointer}
    </style></head><body>

    <div class="topbar">
        <h1>🛡️ Dewgram Admin</h1>
        <div class="toplinks">
            <a href="/{{ secret }}/support">🎫 Tickets</a>
            <a href="/{{ secret }}/logout">Logout</a>
        </div>
    </div>

    <div class="stats">
        <div class="stat"><div class="stat-num">{{ total_users }}</div><div class="stat-lbl">Users</div></div>
        <div class="stat"><div class="stat-num">{{ total_posts }}</div><div class="stat-lbl">Posts</div></div>
        <div class="stat red"><div class="stat-num">{{ banned_count }}</div><div class="stat-lbl">Banned</div></div>
        <div class="stat orange"><div class="stat-num">{{ reports_count }}</div><div class="stat-lbl">Reports</div></div>
    </div>

    <div class="section">
        <div class="section-title">Users Management</div>

        <!-- Filters -->
        <div class="filters">
            <a href="?filter=all&q={{ search }}" class="filter-btn {% if ffilter=='all' %}active{% endif %}">All ({{ total_users }})</a>
            <a href="?filter=active&q={{ search }}" class="filter-btn {% if ffilter=='active' %}active{% endif %}">Active</a>
            <a href="?filter=banned&q={{ search }}" class="filter-btn {% if ffilter=='banned' %}active{% endif %}">Banned ({{ banned_count }})</a>
        </div>

        <form class="search-bar" method="get">
            <input type="hidden" name="filter" value="{{ ffilter }}">
            <input name="q" value="{{ search }}" placeholder="Search username..." autocomplete="off">
            <button type="submit">Search</button>
        </form>

        <table>
            <thead><tr><th>User</th><th>Email</th><th>Posts</th><th>Joined</th><th>Status</th><th>Actions</th></tr></thead>
            <tbody>
            {% for u in users %}
            <tr>
                <td>
                    <div style="display:flex;align-items:center;gap:10px;">
                        {% if u.avatar_url %}<img src="{{ u.avatar_url }}" class="av">
                        {% else %}<div class="avp">{{ u.username[:2].upper() }}</div>{% endif %}
                        <div>
                            <div style="font-weight:700;">@{{ u.username }}</div>
                            {% if u.bio %}<div style="font-size:10px;color:#aaa;">{{ u.bio[:25] }}</div>{% endif %}
                        </div>
                    </div>
                </td>
                <td style="color:#888;font-size:11px;">{{ u.email or '—' }}</td>
                <td style="font-weight:700;">{{ u.posts|length }}</td>
                <td style="color:#bbb;font-size:11px;">{{ u.created_at.strftime('%Y-%m-%d') }}</td>
                <td>
                    {% if u.is_banned %}<span class="badge b-ban">Banned</span>
                    {% else %}<span class="badge b-ok">Active</span>{% endif %}
                    {% if u.is_admin %}<span class="badge b-admin">Admin</span>{% endif %}
                </td>
                <td>
                    {% if u.is_banned %}
                        <a href="/{{ secret }}/unban/{{ u.id }}" class="btn bg">Unban</a>
                    {% else %}
                        <a href="/{{ secret }}/ban/{{ u.id }}" class="btn bo" onclick="return confirm('Ban @{{ u.username }}?')">Ban</a>
                    {% endif %}
                    <button class="btn bb" onclick="openReset({{ u.id }},'{{ u.username }}')">Reset PW</button>
                    <button class="btn bx" onclick="openPosts({{ u.id }},'{{ u.username }}')">Posts</button>
                    <a href="/{{ secret }}/delete-user/{{ u.id }}" class="btn br" onclick="return confirm('DELETE @{{ u.username }}?')">Delete</a>
                </td>
            </tr>
            {% endfor %}
            {% if not users %}
            <tr><td colspan="6" style="text-align:center;color:#aaa;padding:30px;">No users found.</td></tr>
            {% endif %}
            </tbody>
        </table>
    </div>

    <!-- Reset Password Modal -->
    <div class="overlay" id="mReset">
        <div class="modal">
            <h3>🔑 Reset Password</h3>
            <p id="rlabel">New password for user</p>
            <form id="rform" method="post">
                <input type="password" name="new_password" id="rpw" placeholder="New password (min 6 chars)" required minlength="6">
                <div class="mbtns">
                    <button type="button" class="mk" onclick="close_('mReset')">Cancel</button>
                    <button type="submit" class="mc">Reset</button>
                </div>
            </form>
        </div>
    </div>

    <!-- Posts Modal -->
    <div class="overlay" id="mPosts">
        <div class="modal" style="width:500px;max-width:95vw;">
            <h3>📸 Posts</h3>
            <p id="plabel"></p>
            <div class="pgrid" id="pgrid"></div>
            <div style="margin-top:14px;text-align:right;">
                <button class="mk" style="padding:8px 18px;border:none;border-radius:6px;cursor:pointer;font-weight:700;" onclick="close_('mPosts')">Close</button>
            </div>
        </div>
    </div>

    <script>
        const S = "{{ secret }}";
        function openReset(uid,un){
            document.getElementById('rlabel').textContent='Set new password for @'+un;
            document.getElementById('rform').action='/'+S+'/reset-password/'+uid;
            document.getElementById('rpw').value='';
            document.getElementById('mReset').classList.add('on');
        }
        function openPosts(uid,un){
            document.getElementById('plabel').textContent='Posts by @'+un;
            document.getElementById('pgrid').innerHTML='<p style="color:#aaa;font-size:12px;padding:8px;">Loading...</p>';
            document.getElementById('mPosts').classList.add('on');
            fetch('/'+S+'/user-posts/'+uid).then(r=>r.json()).then(d=>{
                if(!d.posts.length){document.getElementById('pgrid').innerHTML='<p style="color:#aaa;font-size:12px;">No posts.</p>';return;}
                document.getElementById('pgrid').innerHTML=d.posts.map(p=>`
                    <div class="pt">
                        ${p.image?`<img src="${p.image}">`:`<div style="width:100%;height:100%;display:flex;align-items:center;justify-content:center;font-size:9px;color:#aaa;padding:4px;text-align:center;">${p.content}</div>`}
                        <button class="dx" onclick="delPost(${p.id},this)">✕</button>
                    </div>`).join('');
            });
        }
        function delPost(pid,btn){
            if(!confirm('Delete this post?'))return;
            fetch('/'+S+'/delete-post/'+pid,{method:'POST'}).then(r=>r.json()).then(d=>{if(d.ok)btn.closest('.pt').remove();});
        }
        function close_(id){document.getElementById(id).classList.remove('on');}
        document.querySelectorAll('.overlay').forEach(m=>m.addEventListener('click',e=>{if(e.target===m)m.classList.remove('on');}));
    </script>
    </body></html>
    """, users=users, total_users=total_users, total_posts=total_posts,
         banned_count=banned_count, reports_count=reports_count,
         search=search, ffilter=ffilter, secret=ADMIN_SECRET_PATH)

    return render_template_string("""
    <!DOCTYPE html><html><head><meta charset="UTF-8">
    <meta name="viewport" content="width=device-width,initial-scale=1">
    <title>Admin Dashboard</title>
    <style>
        *{box-sizing:border-box;margin:0;padding:0}
        body{background:#f0f2f5;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;color:#333}
        .topbar{background:linear-gradient(135deg,#0d0d0d,#1a1a2e);padding:0 24px;height:56px;display:flex;align-items:center;justify-content:space-between;position:sticky;top:0;z-index:100;box-shadow:0 2px 8px rgba(0,0,0,0.4)}
        .topbar h1{color:#fff;font-size:17px;font-weight:700;display:flex;align-items:center;gap:8px}
        .topbar a{color:#aaa;font-size:12px;text-decoration:none;padding:6px 14px;border:1px solid #333;border-radius:4px}
        .topbar a:hover{color:#fff;border-color:#e94560}
        .stats{display:grid;grid-template-columns:repeat(3,1fr);gap:14px;padding:20px 24px 0}
        .stat{background:#fff;border-radius:10px;padding:20px;text-align:center;box-shadow:0 1px 4px rgba(0,0,0,0.08)}
        .stat-num{font-size:30px;font-weight:800;color:#1a1a2e}
        .stat-lbl{font-size:11px;color:#999;margin-top:4px;text-transform:uppercase;letter-spacing:.05em}
        .stat.red .stat-num{color:#e94560}
        .section{padding:20px 24px}
        .section-title{font-size:12px;font-weight:700;color:#999;text-transform:uppercase;letter-spacing:.05em;margin-bottom:12px}
        .search-bar{display:flex;gap:8px;margin-bottom:14px}
        .search-bar input{flex:1;padding:10px 14px;border:1px solid #ddd;border-radius:6px;font-size:13px;outline:none}
        .search-bar input:focus{border-color:#4a8db7}
        .search-bar button{padding:10px 18px;background:#4a8db7;color:#fff;border:none;border-radius:6px;font-size:13px;font-weight:700;cursor:pointer}
        table{width:100%;background:#fff;border-radius:10px;box-shadow:0 1px 4px rgba(0,0,0,0.07);border-collapse:collapse;overflow:hidden}
        th{background:#f8f9fa;padding:11px 14px;text-align:left;font-size:10px;font-weight:700;color:#999;text-transform:uppercase;letter-spacing:.05em;border-bottom:1px solid #eee}
        td{padding:11px 14px;font-size:13px;border-bottom:1px solid #f5f5f5;vertical-align:middle}
        tr:last-child td{border-bottom:none}
        tr:hover td{background:#fafafa}
        .av{width:34px;height:34px;border-radius:50%;object-fit:cover;border:1px solid #ddd}
        .avp{width:34px;height:34px;border-radius:50%;background:#dde;display:inline-flex;align-items:center;justify-content:center;font-size:11px;font-weight:700;color:#556}
        .badge{padding:2px 8px;border-radius:20px;font-size:10px;font-weight:700}
        .b-ban{background:#fff0f0;color:#e94560;border:1px solid #ffc0c0}
        .b-ok{background:#f0fff4;color:#27ae60;border:1px solid #b2dfdb}
        .b-admin{background:#fff8e1;color:#f39c12;border:1px solid #ffe082;margin-left:3px}
        .btn{display:inline-block;padding:5px 10px;border-radius:4px;font-size:11px;font-weight:700;text-decoration:none;cursor:pointer;border:none;margin:1px;white-space:nowrap}
        .br{background:#e94560;color:#fff}.br:hover{background:#c73652}
        .bo{background:#e67e22;color:#fff}.bo:hover{background:#ca6f1e}
        .bg{background:#27ae60;color:#fff}.bg:hover{background:#1e8449}
        .bb{background:#4a8db7;color:#fff}.bb:hover{background:#2a6a96}
        .bx{background:#95a5a6;color:#fff}.bx:hover{background:#7f8c8d}
        .overlay{display:none;position:fixed;inset:0;background:rgba(0,0,0,0.55);z-index:200;align-items:center;justify-content:center}
        .overlay.on{display:flex}
        .modal{background:#fff;border-radius:12px;padding:28px 24px;width:360px;box-shadow:0 8px 32px rgba(0,0,0,0.2)}
        .modal h3{font-size:15px;font-weight:700;margin-bottom:6px}
        .modal p{font-size:12px;color:#777;margin-bottom:18px}
        .modal input{width:100%;padding:10px;border:1px solid #ddd;border-radius:6px;font-size:13px;margin-bottom:12px;outline:none}
        .modal input:focus{border-color:#4a8db7}
        .mbtns{display:flex;gap:8px}
        .mbtns button{flex:1;padding:10px;border:none;border-radius:6px;font-size:13px;font-weight:700;cursor:pointer}
        .mc{background:#e94560;color:#fff}.mk{background:#eee;color:#555}
        .pgrid{display:grid;grid-template-columns:repeat(auto-fill,minmax(90px,1fr));gap:6px;margin-top:10px;max-height:320px;overflow-y:auto}
        .pt{position:relative;aspect-ratio:1;border-radius:6px;overflow:hidden;background:#ddd}
        .pt img{width:100%;height:100%;object-fit:cover}
        .pt .dx{position:absolute;top:3px;right:3px;background:rgba(233,69,96,.9);color:#fff;border:none;border-radius:3px;padding:2px 5px;font-size:9px;font-weight:700;cursor:pointer}
        .lock-badge{display:inline-flex;align-items:center;gap:5px;background:#e8f4fd;border:1px solid #b3d9f7;border-radius:6px;padding:4px 10px;font-size:11px;color:#1a6a9a;margin-bottom:12px}
    </style></head><body>

    <div class="topbar">
        <h1>🛡️ Admin Dashboard</h1>
        <div style="display:flex;align-items:center;gap:12px;">
            <a href="/{{ secret }}/support" style="color:#aaa;font-size:12px;text-decoration:none;padding:6px 14px;border:1px solid #333;border-radius:4px;">🎫 Support Tickets</a>
            <span style="color:#555;font-size:11px;">🔐 Secure session</span>
            <a href="/{{ secret }}/logout">Logout</a>
        </div>
    </div>

    <div class="stats">
        <div class="stat"><div class="stat-num">{{ total_users }}</div><div class="stat-lbl">Total Users</div></div>
        <div class="stat"><div class="stat-num">{{ total_posts }}</div><div class="stat-lbl">Total Posts</div></div>
        <div class="stat red"><div class="stat-num">{{ banned_count }}</div><div class="stat-lbl">Banned</div></div>
    </div>

    <div class="section">
        <div class="section-title">Users Management</div>
        <form class="search-bar" method="get">
            <input name="q" value="{{ search }}" placeholder="Search username..." autocomplete="off">
            <button type="submit">Search</button>
        </form>
        <table>
            <thead><tr>
                <th>User</th><th>Email</th><th>Posts</th><th>Joined</th><th>Status</th><th>Actions</th>
            </tr></thead>
            <tbody>
            {% for u in users %}
            <tr>
                <td>
                    <div style="display:flex;align-items:center;gap:10px;">
                        {% if u.avatar_filename %}
                            <img src="/uploads/{{ u.avatar_filename }}" class="av">
                        {% else %}
                            <div class="avp">{{ u.username[:2].upper() }}</div>
                        {% endif %}
                        <div>
                            <div style="font-weight:700;">@{{ u.username }}</div>
                            {% if u.bio %}<div style="font-size:10px;color:#aaa;">{{ u.bio[:25] }}</div>{% endif %}
                        </div>
                    </div>
                </td>
                <td style="color:#888;font-size:11px;">{{ u.email or '—' }}</td>
                <td style="font-weight:700;">{{ u.posts|length }}</td>
                <td style="color:#bbb;font-size:11px;">{{ u.created_at.strftime('%Y-%m-%d') }}</td>
                <td>
                    {% if u.is_banned %}<span class="badge b-ban">Banned</span>
                    {% else %}<span class="badge b-ok">Active</span>{% endif %}
                    {% if u.is_admin %}<span class="badge b-admin">Admin</span>{% endif %}
                </td>
                <td>
                    {% if u.is_banned %}
                        <a href="/{{ secret }}/unban/{{ u.id }}" class="btn bg" onclick="return confirm('Unban @{{ u.username }}?')">Unban</a>
                    {% else %}
                        <a href="/{{ secret }}/ban/{{ u.id }}" class="btn bo" onclick="return confirm('Ban @{{ u.username }}?')">Ban</a>
                    {% endif %}
                    <button class="btn bb" onclick="openReset({{ u.id }},'{{ u.username }}')">Reset PW</button>
                    <button class="btn bx" onclick="openPosts({{ u.id }},'{{ u.username }}')">Posts</button>
                    <a href="/{{ secret }}/delete-user/{{ u.id }}" class="btn br" onclick="return confirm('DELETE @{{ u.username }}? Cannot be undone!')">Delete</a>
                </td>
            </tr>
            {% endfor %}
            </tbody>
        </table>
    </div>

    <!-- Reset Password Modal -->
    <div class="overlay" id="mReset">
        <div class="modal">
            <h3>🔑 Reset Password</h3>
            <p id="rlabel">New password for user</p>
            <form id="rform" method="post">
                <input type="password" name="new_password" id="rpw" placeholder="New password (min 6 chars)" required minlength="6">
                <div class="mbtns">
                    <button type="button" class="mk" onclick="close_('mReset')">Cancel</button>
                    <button type="submit" class="mc">Reset</button>
                </div>
            </form>
        </div>
    </div>

    <!-- Posts Modal -->
    <div class="overlay" id="mPosts">
        <div class="modal" style="width:480px;max-width:95vw;">
            <h3>📸 User Posts</h3>
            <p id="plabel"></p>
            <div class="pgrid" id="pgrid"></div>
            <div style="margin-top:14px;text-align:right;">
                <button class="mk" style="padding:8px 18px;border:none;border-radius:6px;cursor:pointer;font-weight:700;" onclick="close_('mPosts')">Close</button>
            </div>
        </div>
    </div>

    <script>
        const S = "{{ secret }}";
        function openReset(uid,un){
            document.getElementById('rlabel').textContent='Set new password for @'+un;
            document.getElementById('rform').action='/'+S+'/reset-password/'+uid;
            document.getElementById('rpw').value='';
            document.getElementById('mReset').classList.add('on');
        }
        function openPosts(uid,un){
            document.getElementById('plabel').textContent='Posts by @'+un;
            document.getElementById('pgrid').innerHTML='<p style="color:#aaa;font-size:12px;padding:8px;">Loading...</p>';
            document.getElementById('mPosts').classList.add('on');
            fetch('/'+S+'/user-posts/'+uid)
                .then(r=>r.json())
                .then(d=>{
                    if(!d.posts.length){document.getElementById('pgrid').innerHTML='<p style="color:#aaa;font-size:12px;padding:8px;">No posts.</p>';return;}
                    document.getElementById('pgrid').innerHTML=d.posts.map(p=>`
                        <div class="pt">
                            ${p.image?`<img src="/uploads/${p.image}">`:`<div style="width:100%;height:100%;display:flex;align-items:center;justify-content:center;font-size:9px;color:#aaa;padding:4px;text-align:center;">${p.content}</div>`}
                            <button class="dx" onclick="delPost(${p.id},this)">✕</button>
                        </div>`).join('');
                });
        }
        function delPost(pid,btn){
            if(!confirm('Delete this post?'))return;
            fetch('/'+S+'/delete-post/'+pid,{method:'POST'})
                .then(r=>r.json()).then(d=>{if(d.ok)btn.closest('.pt').remove();});
        }
        function close_(id){document.getElementById(id).classList.remove('on');}
        document.querySelectorAll('.overlay').forEach(m=>m.addEventListener('click',e=>{if(e.target===m)m.classList.remove('on');}));
    </script>
    </body></html>
    """, users=users, total_users=total_users, total_posts=total_posts,
         banned_count=banned_count, search=search, secret=ADMIN_SECRET_PATH)


@admin_bp.route(f"/{ADMIN_SECRET_PATH}/ban/<int:uid>")
@admin_required
def admin_ban(uid):
    u = User.query.get_or_404(uid)
    u.is_banned = True
    db.session.commit()
    return redirect(f"/{ADMIN_SECRET_PATH}/")

@admin_bp.route(f"/{ADMIN_SECRET_PATH}/unban/<int:uid>")
@admin_required
def admin_unban(uid):
    u = User.query.get_or_404(uid)
    u.is_banned = False
    db.session.commit()
    return redirect(f"/{ADMIN_SECRET_PATH}/")

@admin_bp.route(f"/{ADMIN_SECRET_PATH}/delete-user/<int:uid>")
@admin_required
def admin_delete_user(uid):
    u = User.query.get_or_404(uid)
    if u.avatar_filename:
        try: os.remove(os.path.join(current_app.config['UPLOAD_FOLDER'], u.avatar_filename))
        except: pass
    for p in u.posts:
        if p.image_filename:
            try: os.remove(os.path.join(current_app.config['UPLOAD_FOLDER'], p.image_filename))
            except: pass
    db.session.delete(u)
    db.session.commit()
    return redirect(f"/{ADMIN_SECRET_PATH}/")

@admin_bp.route(f"/{ADMIN_SECRET_PATH}/reset-password/<int:uid>", methods=["POST"])
@admin_required
def admin_reset_password(uid):
    u = User.query.get_or_404(uid)
    pw = request.form.get("new_password","").strip()
    if len(pw) >= 6:
        u.password_hash = generate_password_hash(pw)
        db.session.commit()
    return redirect(f"/{ADMIN_SECRET_PATH}/")

@admin_bp.route(f"/{ADMIN_SECRET_PATH}/delete-post/<int:pid>", methods=["POST"])
@admin_required
def admin_delete_post(pid):
    # from flask import jsonify
    p = Post.query.get_or_404(pid)
    if p.image_filename:
        try: os.remove(os.path.join(current_app.config['UPLOAD_FOLDER'], p.image_filename))
        except: pass
    db.session.delete(p)
    db.session.commit()
    return jsonify({"ok": True})

@admin_bp.route(f"/{ADMIN_SECRET_PATH}/support")
@admin_required
def admin_support():
    tickets = SupportTicket.query.order_by(SupportTicket.created_at.desc()).all()
    return render_template_string("""
    <!DOCTYPE html><html><head><meta charset="UTF-8">
    <meta name="viewport" content="width=device-width,initial-scale=1">
    <title>Support Tickets</title>
    <style>
        *{box-sizing:border-box;margin:0;padding:0}
        body{background:#f0f2f5;font-family:-apple-system,sans-serif}
        .topbar{background:linear-gradient(135deg,#0d0d0d,#1a1a2e);padding:0 20px;height:52px;display:flex;align-items:center;justify-content:space-between;position:sticky;top:0;z-index:100}
        .topbar h1{color:#fff;font-size:16px;font-weight:700}
        .topbar a{color:#aaa;font-size:12px;text-decoration:none;padding:5px 12px;border:1px solid #333;border-radius:4px}
        .topbar a:hover{color:#fff}
        .section{padding:20px}
        table{width:100%;background:#fff;border-radius:10px;box-shadow:0 1px 4px rgba(0,0,0,.07);border-collapse:collapse;overflow:hidden}
        th{background:#f8f9fa;padding:11px 14px;text-align:left;font-size:10px;font-weight:700;color:#999;text-transform:uppercase;letter-spacing:.05em;border-bottom:1px solid #eee}
        td{padding:11px 14px;font-size:13px;border-bottom:1px solid #f5f5f5;vertical-align:middle}
        tr:last-child td{border-bottom:none}
        tr:hover td{background:#fafafa}
        .st-open{background:#e8f4fd;color:#1a6a9a;padding:2px 8px;border-radius:20px;font-size:10px;font-weight:700}
        .st-replied{background:#e8fdf0;color:#27ae60;padding:2px 8px;border-radius:20px;font-size:10px;font-weight:700}
        .st-closed{background:#f5f5f5;color:#888;padding:2px 8px;border-radius:20px;font-size:10px;font-weight:700}
        .btn{display:inline-block;padding:5px 10px;border-radius:4px;font-size:11px;font-weight:700;text-decoration:none;cursor:pointer;border:none;margin:1px}
        .bb{background:#4a8db7;color:#fff}.bg{background:#27ae60;color:#fff}.bx{background:#95a5a6;color:#fff}
    </style></head><body>
    <div class="topbar">
        <h1>🎫 Support Tickets</h1>
        <a href="/{{ secret }}/">← Dashboard</a>
    </div>
    <div class="section">
        <table>
            <thead><tr><th>#</th><th>User</th><th>Subject</th><th>Date</th><th>Status</th><th>Action</th></tr></thead>
            <tbody>
            {% for t in tickets %}
            <tr>
                <td style="color:#aaa;font-size:11px;">#{{ t.id }}</td>
                <td style="font-weight:700;">@{{ t.user.username }}</td>
                <td>{{ t.subject[:60] }}</td>
                <td style="color:#aaa;font-size:11px;">{{ t.created_at.strftime('%Y-%m-%d %H:%M') }}</td>
                <td><span class="st-{{ t.status }}">{{ t.status }}</span></td>
                <td>
                    <a href="/{{ secret }}/support/{{ t.id }}" class="btn bb">View & Reply</a>
                    <a href="/{{ secret }}/support/{{ t.id }}/close" class="btn bx">Close</a>
                </td>
            </tr>
            {% else %}
            <tr><td colspan="6" style="text-align:center;color:#aaa;padding:30px;">No tickets yet.</td></tr>
            {% endfor %}
            </tbody>
        </table>
    </div>
    </body></html>
    """, tickets=tickets, secret=ADMIN_SECRET_PATH)


@admin_bp.route(f"/{ADMIN_SECRET_PATH}/support/<int:tid>", methods=["GET","POST"])
@admin_required
def admin_ticket(tid):
    ticket = SupportTicket.query.get_or_404(tid)
    if request.method == "POST":
        body = request.form.get("body","").strip()
        if body:
            msg = SupportMessage(ticket_id=tid, sender_id=None, body=body, is_admin=True)
            ticket.status = "replied"
            db.session.add(msg)
            db.session.commit()
        return redirect(url_for('admin.admin_ticket', tid=tid))
    return render_template_string("""
    <!DOCTYPE html><html><head><meta charset="UTF-8">
    <meta name="viewport" content="width=device-width,initial-scale=1">
    <title>Ticket #{{ ticket.id }}</title>
    <style>
        *{box-sizing:border-box;margin:0;padding:0}
        body{background:#f0f2f5;font-family:-apple-system,sans-serif}
        .topbar{background:linear-gradient(135deg,#0d0d0d,#1a1a2e);padding:0 20px;height:52px;display:flex;align-items:center;gap:14px;position:sticky;top:0;z-index:100}
        .topbar h1{color:#fff;font-size:15px;font-weight:700;flex:1}
        .topbar a{color:#aaa;font-size:12px;text-decoration:none;padding:5px 12px;border:1px solid #333;border-radius:4px}
        .msgs{padding:20px;display:flex;flex-direction:column;gap:12px;padding-bottom:100px}
        .bbl{max-width:70%;padding:12px 16px;border-radius:10px;font-size:13px;line-height:1.6}
        .bbl-user{background:white;border:1px solid #ddd;border-radius:10px 10px 10px 0;align-self:flex-start}
        .bbl-admin{background:linear-gradient(135deg,#1a1a2e,#0d3460);color:white;border-radius:10px 10px 0 10px;align-self:flex-end}
        .who{font-size:10px;color:#aaa;margin-bottom:4px}
        .who-admin{color:rgba(255,255,255,.6)}
        .reply-bar{position:fixed;bottom:0;left:0;right:0;background:#f5f5f5;border-top:1px solid #ddd;padding:12px 20px;display:flex;gap:10px}
        .reply-bar input{flex:1;padding:11px 14px;border:1px solid #ccc;border-radius:6px;font-size:13px;outline:none}
        .reply-bar button{padding:11px 20px;background:#e94560;color:white;border:none;border-radius:6px;font-weight:700;cursor:pointer}
    </style></head><body>
    <div class="topbar">
        <a href="/{{ secret }}/support">← Tickets</a>
        <h1>@{{ ticket.user.username }} — {{ ticket.subject[:40] }}</h1>
    </div>
    <div class="msgs">
        {% for m in ticket.messages %}
        <div class="bbl {{ 'bbl-admin' if m.is_admin else 'bbl-user' }}">
            <div class="who {{ 'who-admin' if m.is_admin else '' }}">
                {% if m.is_admin %}Support Team (Admin){% else %}@{{ ticket.user.username }}{% endif %}
                · {{ m.created_at.strftime('%b %d %H:%M') }}
            </div>
            {{ m.body }}
        </div>
        {% endfor %}
    </div>
    <form method="post" class="reply-bar">
        <input name="body" placeholder="Reply as support team..." required autocomplete="off">
        <button type="submit">Send</button>
    </form>
    </body></html>
    """, ticket=ticket, secret=ADMIN_SECRET_PATH)


@admin_bp.route(f"/{ADMIN_SECRET_PATH}/support/<int:tid>/close")
@admin_required
def admin_close_ticket(tid):
    ticket = SupportTicket.query.get_or_404(tid)
    ticket.status = "closed"
    db.session.commit()
    return redirect(url_for('admin.admin_support'))


@admin_bp.route(f"/{ADMIN_SECRET_PATH}/user-posts/<int:uid>")
@admin_required
def admin_user_posts(uid):
    # from flask import jsonify
    u = User.query.get_or_404(uid)
    posts = [{"id": p.id, "image": p.image_filename, "content": (p.content or '')[:30]} for p in u.posts]
    return jsonify({"posts": posts})



# ── دعم المستخدمين ─────────────────────────────────────────
