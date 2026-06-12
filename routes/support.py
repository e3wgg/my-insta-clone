from flask import Blueprint, request, redirect, url_for, render_template_string
from flask_login import login_required, current_user
from extensions import db
from models import SupportTicket, SupportMessage

support = Blueprint('support', __name__)


@support.route("/support", methods=["GET","POST"])
def support_page():
    sent = False
    if request.method == "POST":
        subject = request.form.get("subject","").strip()
        body    = request.form.get("body","").strip()
        uid = current_user.id if current_user.is_authenticated else None
        if subject and body and uid:
            ticket = SupportTicket(user_id=uid, subject=subject)
            db.session.add(ticket); db.session.flush()
            db.session.add(SupportMessage(ticket_id=ticket.id, sender_id=uid, body=body, is_admin=False))
            db.session.commit()
            sent = True

    my_tickets = SupportTicket.query.filter_by(user_id=current_user.id).order_by(SupportTicket.created_at.desc()).all() if current_user.is_authenticated else []

    return render_template_string("""
    <!DOCTYPE html><html><head><meta charset="UTF-8">
    <meta name="viewport" content="width=device-width,initial-scale=1">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        *{box-sizing:border-box;margin:0;padding:0}body{background:#d8dadb;font-family:-apple-system,sans-serif;max-width:480px;margin:0 auto}
        .hdr{background:linear-gradient(to bottom,#4a8db7,#2a6a96);display:flex;align-items:center;height:48px;padding:0 14px;position:sticky;top:0}
        .hdr a{color:white;font-size:17px;margin-right:12px;text-decoration:none}
        .hdr span{color:white;font-weight:700;font-size:15px;text-transform:uppercase;letter-spacing:.04em}
        .card{background:white;border:1px solid #d0d0d0;border-radius:6px;margin:14px;overflow:hidden}
        input,textarea{width:100%;padding:11px 14px;border:none;border-bottom:1px solid #eee;font-size:13px;outline:none;font-family:inherit;background:#fafafa}
        textarea{resize:none;height:100px}
        .sbtn{display:block;width:calc(100% - 28px);margin:0 14px 14px;padding:13px;background:linear-gradient(to bottom,#6dbf67,#4caf50);color:white;font-weight:700;font-size:14px;border:none;border-radius:4px;cursor:pointer}
        .ticket{padding:12px 14px;border-bottom:1px solid #f0f0f0;display:flex;justify-content:space-between;align-items:center;text-decoration:none;color:#333}
        .st-open{background:#e8f4fd;color:#1a6a9a;padding:2px 8px;border-radius:20px;font-size:10px;font-weight:700}
        .st-replied{background:#e8fdf0;color:#27ae60;padding:2px 8px;border-radius:20px;font-size:10px;font-weight:700}
        .st-closed{background:#f5f5f5;color:#888;padding:2px 8px;border-radius:20px;font-size:10px;font-weight:700}
        .success{background:#e8fdf0;border:1px solid #b2dfdb;border-radius:6px;padding:14px;margin:14px;text-align:center;color:#27ae60;font-size:13px;font-weight:700}
    </style></head><body>
    <div class="hdr"><a href="javascript:history.back()"><i class="fa-solid fa-chevron-left"></i></a><span>Support</span></div>
    {% if sent %}<div class="success"><i class="fa-solid fa-circle-check" style="margin-right:6px;"></i>Ticket sent!</div>{% endif %}
    {% if current_user.is_authenticated %}
    <div style="padding:14px 14px 0;font-size:13px;color:#555;">Hi <strong>@{{ current_user.username }}</strong>, describe your issue:</div>
    <div class="card" style="margin-top:10px;">
        <form method="post">
            <input name="subject" placeholder="Subject" required maxlength="200">
            <textarea name="body" placeholder="Describe your issue..." required></textarea>
            <div style="height:8px;"></div>
        </form>
    </div>
    <button class="sbtn" onclick="this.closest('body').querySelector('form').submit()">Send Message</button>
    {% if my_tickets %}
    <div style="padding:0 14px 6px;font-size:11px;font-weight:700;color:#888;text-transform:uppercase;">Your Tickets</div>
    <div class="card" style="margin-top:0;">
        {% for t in my_tickets %}
        <a href="{{ url_for('support.ticket_view', tid=t.id) }}" class="ticket">
            <div><div style="font-size:13px;font-weight:600;">{{ t.subject[:50] }}</div><div style="font-size:10px;color:#aaa;">{{ t.created_at.strftime('%Y-%m-%d %H:%M') }}</div></div>
            <span class="st-{{ t.status }}">{{ t.status }}</span>
        </a>
        {% endfor %}
    </div>
    {% endif %}
    {% else %}
    <div style="padding:30px;text-align:center;color:#888;font-size:13px;">
        <i class="fa-regular fa-envelope" style="font-size:36px;display:block;margin-bottom:12px;color:#4a8db7;"></i>
        Please <a href="/login" style="color:#4a8db7;font-weight:700;">sign in</a> to contact support.
    </div>
    {% endif %}
    </body></html>""", sent=sent, my_tickets=my_tickets, current_user=current_user)


@support.route("/support/ticket/<int:tid>", methods=["GET","POST"])
@login_required
def ticket_view(tid):
    ticket = SupportTicket.query.get_or_404(tid)
    if ticket.user_id != current_user.id:
        return redirect(url_for('support.support_page'))
    if request.method == "POST":
        body = request.form.get("body","").strip()
        if body:
            ticket.status = "open"
            db.session.add(SupportMessage(ticket_id=tid, sender_id=current_user.id, body=body, is_admin=False))
            db.session.commit()
        return redirect(url_for('support.ticket_view', tid=tid))

    return render_template_string("""
    <!DOCTYPE html><html><head><meta charset="UTF-8">
    <meta name="viewport" content="width=device-width,initial-scale=1">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        *{box-sizing:border-box;margin:0;padding:0}body{background:#d8dadb;font-family:-apple-system,sans-serif;max-width:480px;margin:0 auto}
        .hdr{background:linear-gradient(to bottom,#4a8db7,#2a6a96);display:flex;align-items:center;height:48px;padding:0 14px;position:sticky;top:0}
        .hdr a{color:white;font-size:17px;margin-right:12px;text-decoration:none}
        .hdr span{color:white;font-weight:700;font-size:14px}
        .msgs{padding:12px;display:flex;flex-direction:column;gap:10px;padding-bottom:80px}
        .bbl{max-width:80%;padding:10px 14px;border-radius:10px;font-size:13px;line-height:1.5}
        .bu{background:white;border:1px solid #ddd;align-self:flex-start;border-radius:10px 10px 10px 0}
        .ba{background:linear-gradient(to bottom,#4a8db7,#2a6a96);color:white;align-self:flex-end;border-radius:10px 10px 0 10px}
        .who{font-size:10px;color:#aaa;margin-bottom:3px}.wa{color:rgba(255,255,255,.7)}
        .rb{position:fixed;bottom:0;left:0;right:0;max-width:480px;margin:0 auto;background:#f5f5f5;border-top:1px solid #ddd;padding:10px 12px;display:flex;gap:8px}
        .rb input{flex:1;padding:10px;border:1px solid #ccc;border-radius:4px;font-size:13px;outline:none}
        .rb button{padding:10px 16px;background:#4a8db7;color:white;border:none;border-radius:4px;font-weight:700;cursor:pointer}
    </style></head><body>
    <div class="hdr"><a href="/support"><i class="fa-solid fa-chevron-left"></i></a><span>{{ ticket.subject[:40] }}</span></div>
    <div class="msgs">
        {% for m in ticket.messages %}
        <div class="bbl {{ 'ba' if m.is_admin else 'bu' }}">
            <div class="who {{ 'wa' if m.is_admin else '' }}">{% if m.is_admin %}Support Team{% else %}You{% endif %} · {{ m.created_at.strftime('%b %d %H:%M') }}</div>
            {{ m.body }}
        </div>
        {% endfor %}
    </div>
    <form method="post" class="rb">
        <input name="body" placeholder="Reply..." required autocomplete="off">
        <button type="submit">Send</button>
    </form>
    </body></html>""", ticket=ticket, current_user=current_user)
