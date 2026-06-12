import os
from flask import Blueprint, request, redirect, url_for, render_template_string
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from datetime import datetime, timezone
from extensions import db
from models import User, Message
from layout import get_layout

messages = Blueprint('messages', __name__)


@messages.route("/messages")
@login_required
def inbox():
    blocked_ids = {b.blocked_id for b in current_user.blocking}
    blocker_ids = {b.blocker_id for b in current_user.blocked_by}
    hidden      = blocked_ids | blocker_ids
    all_users   = User.query.filter(User.id != current_user.id, ~User.id.in_(hidden)).all()
    unread      = {u.id: Message.query.filter_by(sender_id=u.id, receiver_id=current_user.id, is_read=False).count() for u in all_users}

    content_html = """
    <div style="background:#f0f0f0;min-height:100vh;padding-bottom:60px;">
        <div style="padding:10px 14px 4px;font-size:11px;font-weight:700;color:#888;text-transform:uppercase;letter-spacing:.05em;border-bottom:1px solid #ddd;">Direct Inbox</div>
        {% for u in users %}
        <a href="{{ url_for('messages.chat', user_id=u.id) }}" style="display:flex;align-items:center;justify-content:space-between;padding:12px 14px;background:white;border-bottom:1px solid #e8e8e8;text-decoration:none;">
            <div style="display:flex;align-items:center;gap:12px;">
                {% if u.avatar_filename %}
                    <img src="{{ u.avatar_url or "/uploads/" + (u.avatar_filename or "") }}" style="width:42px;height:42px;border-radius:50%;object-fit:cover;border:1px solid #ddd;">
                {% else %}
                    <div style="width:42px;height:42px;border-radius:50%;background:#c5cae9;display:flex;align-items:center;justify-content:center;font-size:14px;font-weight:700;color:#5c6bc0;border:1px solid #ccc;">{{ u.username[:2].upper() }}</div>
                {% endif %}
                <span style="font-size:13px;font-weight:{% if unread[u.id] > 0 %}800{% else %}600{% endif %};color:#222;">@{{ u.username }}</span>
            </div>
            <div style="display:flex;align-items:center;gap:8px;">
                {% if unread[u.id] > 0 %}
                <span style="background:#e74c3c;color:white;border-radius:50%;width:20px;height:20px;display:flex;align-items:center;justify-content:center;font-size:11px;font-weight:700;">{{ unread[u.id] }}</span>
                {% endif %}
                <span style="font-size:12px;color:#aaa;border:1px solid #ccc;padding:4px 10px;border-radius:3px;background:#f8f8f8;">Open</span>
            </div>
        </a>
        {% else %}
        <div style="padding:40px;text-align:center;color:#aaa;font-size:13px;">No conversations yet.</div>
        {% endfor %}
    </div>
    """
    full_html = get_layout(content_html, active_tab='messages', title='Direct')
    return render_template_string(full_html, users=all_users, unread=unread, current_user=current_user)


@messages.route("/messages/<int:user_id>", methods=["GET","POST"])
@login_required
def chat(user_id):
    from flask import current_app
    recipient = User.query.get_or_404(user_id)
    if current_user.is_blocking(recipient) or recipient.is_blocking(current_user):
        return redirect(url_for('messages.inbox'))

    if request.method == "POST":
        body = request.form.get("body","").strip()
        file = request.files.get("dm_file")
        image_url = image_public_id = resource_type = None

        if file and file.filename:
            from cloudinary_helper import upload_file
            result = upload_file(file, folder="dm")
            if result:
                image_url       = result["url"]
                image_public_id = result["public_id"]
                resource_type   = result["resource_type"]

        if body or image_url:
            db.session.add(Message(
                sender_id=current_user.id, receiver_id=recipient.id,
                body=body, image_url=image_url,
                image_public_id=image_public_id,
                resource_type=resource_type or "image"
            ))
            db.session.commit()
        return redirect(url_for('messages.chat', user_id=user_id))

    Message.query.filter_by(sender_id=recipient.id, receiver_id=current_user.id, is_read=False).update({"is_read": True})
    db.session.commit()
    msgs = Message.query.filter(
        ((Message.sender_id==current_user.id)&(Message.receiver_id==recipient.id))|
        ((Message.sender_id==recipient.id)&(Message.receiver_id==current_user.id))
    ).order_by(Message.timestamp.asc()).all()

    return render_template_string("""
    <!DOCTYPE html><html><head><meta charset="UTF-8">
    <meta name="viewport" content="width=device-width,initial-scale=1">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        *{box-sizing:border-box;margin:0;padding:0}body{background:#edeff1;font-family:-apple-system,sans-serif;max-width:480px;margin:0 auto;min-height:100vh}
        .hdr{background:linear-gradient(to bottom,#4a8db7,#2a6a96);display:flex;align-items:center;height:48px;padding:0 14px;position:sticky;top:0;z-index:50}
        .hdr a{color:white;text-decoration:none;font-size:17px}.name{flex:1;text-align:center;color:white;font-weight:700;font-size:14px}
        .msgs{padding:12px;display:flex;flex-direction:column;gap:10px;padding-bottom:100px;min-height:calc(100vh - 48px)}
        .row-me{display:flex;justify-content:flex-end;gap:8px;align-items:flex-end}
        .row-them{display:flex;justify-content:flex-start;gap:8px;align-items:flex-end}
        .bbl{max-width:75%;padding:9px 13px;font-size:13px;line-height:1.5;word-break:break-word}
        .bbl-me{background:linear-gradient(to bottom,#e1f1ff,#d2e9ff);border:1px solid #baccdc;border-radius:12px 12px 0 12px}
        .bbl-them{background:white;border:1px solid #ddd;border-radius:12px 12px 12px 0}
        .ts{font-size:9px;color:#bbb;margin-top:3px;text-align:right}
        .av{width:28px;height:28px;border-radius:50%;object-fit:cover;border:1px solid #ddd;flex-shrink:0}
        .avp{width:28px;height:28px;border-radius:50%;background:#c5cae9;display:flex;align-items:center;justify-content:center;font-size:9px;font-weight:700;color:#5c6bc0;flex-shrink:0}
        .input-bar{position:fixed;bottom:0;left:0;right:0;max-width:480px;margin:0 auto;background:#f5f5f5;border-top:1px solid #ddd;padding:8px 12px}
        .input-row{display:flex;gap:8px;align-items:center}
        .input-row input[type=text]{flex:1;padding:10px 12px;border:1px solid #ccc;border-radius:20px;font-size:13px;outline:none;background:white}
        .input-row button{padding:10px 16px;background:#4a8db7;color:white;border:none;border-radius:20px;font-weight:700;font-size:13px;cursor:pointer}
        .mp{max-width:200px;border-radius:8px;overflow:hidden;border:1px solid #ddd;margin-bottom:4px}
        .mp img,.mp video{width:100%;display:block}
    </style></head><body>
    <div class="hdr">
        <a href="/messages" style="margin-right:10px;"><i class="fa-solid fa-chevron-left"></i></a>
        <a href="/user/{{ recipient.username }}" class="name">@{{ recipient.username }}</a>
    </div>
    <div class="msgs" id="msgs">
        {% for msg in msgs %}{% set me=msg.sender_id==current_user.id %}
        <div class="{{ 'row-me' if me else 'row-them' }}">
            {% if not me %}{% if recipient.avatar_filename %}<img src="{{ recipient.avatar_url or "/uploads/" + (recipient.avatar_filename or "") }}" class="av">{% else %}<div class="avp">{{ recipient.username[:2].upper() }}</div>{% endif %}{% endif %}
            <div>
                {% if msg.image_filename %}{% set ext=msg.image_filename.rsplit('.',1)[-1].lower() %}
                <div class="mp">{% if ext in ['mp4','mov','avi','mkv'] %}<video controls><source src="{{ msg.image_url or "/uploads/" + (msg.image_filename or "") }}"></video>{% else %}<img src="{{ msg.image_url or "/uploads/" + (msg.image_filename or "") }}">{% endif %}</div>
                {% endif %}
                {% if msg.body %}<div class="bbl {{ 'bbl-me' if me else 'bbl-them' }}">{{ msg.body }}</div>{% endif %}
                <div class="ts">{{ msg.timestamp.strftime('%H:%M') }}</div>
            </div>
            {% if me %}{% if current_user.avatar_filename %}<img src="{{ current_user.avatar_url or "/uploads/" + (current_user.avatar_filename or "") }}" class="av">{% else %}<div class="avp">{{ current_user.username[:2].upper() }}</div>{% endif %}{% endif %}
        </div>
        {% endfor %}
    </div>
    <form method="post" enctype="multipart/form-data" class="input-bar">
        <div style="margin-bottom:6px;display:none;" id="pa"></div>
        <div class="input-row">
            <label style="background:none;border:none;cursor:pointer;color:#888;font-size:18px;padding:4px;">
                <i class="fa-solid fa-image"></i>
                <input type="file" name="dm_file" accept="image/*,video/*" style="display:none" onchange="pf(this)">
            </label>
            <input type="text" name="body" placeholder="Message..." autocomplete="off">
            <button type="submit">Send</button>
        </div>
    </form>
    <script>
        document.getElementById('msgs').scrollTop=9999;
        function pf(i){const f=i.files[0];if(!f)return;const p=document.getElementById('pa');p.style.display='block';const r=new FileReader();r.onload=e=>{p.innerHTML=f.type.startsWith('video')?`<video style="max-width:80px;border-radius:4px;" controls><source src="${e.target.result}"></video>`:`<img src="${e.target.result}" style="max-width:80px;border-radius:4px;border:1px solid #ddd;">`;};r.readAsDataURL(f);}
    </script>
    </body></html>""", recipient=recipient, msgs=msgs, current_user=current_user)
