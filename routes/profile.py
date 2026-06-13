from flask import Blueprint, request, redirect, url_for, render_template_string
from flask_login import login_required, current_user
from extensions import db
from models import User, Notification, Block, Report, SupportTicket, SupportMessage, SavedPost
from layout import get_layout

profile = Blueprint('profile', __name__)


@profile.route("/user/<username>")
@login_required
def profile_view(username):
    user         = User.query.filter_by(username=username).first_or_404()
    show_list    = request.args.get('list', None)
    active_tab_p = request.args.get('tab', 'posts')   # posts / saved
    is_me        = (user.id == current_user.id)
    i_block      = current_user.is_blocking(user)
    they_block   = user.is_blocking(current_user)

    posts_count     = len(user.posts)
    followers_count = user.followers.count()
    following_count = user.followed.count()
    followers_list  = user.followers.all()
    following_list  = user.followed.all()
    saved_posts     = SavedPost.query.filter_by(user_id=user.id)\
                        .order_by(SavedPost.created_at.desc()).all() if is_me else []

    # ── Three-dots menu ──────────────────────────────────────
    if is_me:
        dots_link = '<a href="/settings" style="color:white;font-size:17px;text-decoration:none;"><i class="fa-solid fa-ellipsis-vertical"></i></a>'
    else:
        unblock_html = f'<a href="/unblock/{user.username}" style="display:flex;align-items:center;gap:10px;padding:12px 14px;font-size:13px;color:#555;text-decoration:none;"><i class=\"fa-solid fa-ban\"></i> Unblock</a>'
        block_html   = f'<a href="/block/{user.username}" onclick="return confirm(\'Block @{user.username}?\')" style="display:flex;align-items:center;gap:10px;padding:12px 14px;font-size:13px;color:#555;text-decoration:none;"><i class=\"fa-solid fa-ban\"></i> Block</a>'
        block_item   = unblock_html if i_block else block_html
        dots_link = f'''<div style="position:relative;">
            <button onclick="var m=document.getElementById('dmenu_{user.id}');m.style.display=m.style.display==='block'?'none':'block';"
                    style="background:none;border:none;color:white;font-size:17px;cursor:pointer;padding:4px;">
                <i class="fa-solid fa-ellipsis-vertical"></i>
            </button>
            <div id="dmenu_{user.id}" style="display:none;position:absolute;right:0;top:28px;background:white;border:1px solid #ddd;border-radius:6px;box-shadow:0 4px 12px rgba(0,0,0,.15);min-width:160px;z-index:100;">
                <a href="/report/{user.username}" style="display:flex;align-items:center;gap:10px;padding:12px 14px;font-size:13px;color:#e74c3c;text-decoration:none;border-bottom:1px solid #f0f0f0;">
                    <i class="fa-solid fa-flag"></i> Report
                </a>
                {block_item}
            </div>
        </div>'''

    # ── No back arrow on own profile ─────────────────────────
    back_arrow = '' if is_me else '<a href="javascript:history.back()" style="color:white;font-size:17px;margin-right:10px;text-decoration:none;"><i class="fa-solid fa-chevron-left"></i></a>'

    full_html = get_layout("__PROFILE_PLACEHOLDER__",
                           active_tab='profile', title=user.username.upper(),
                           dots_link=dots_link, back_arrow=back_arrow)

    return render_template_string(full_html.replace("__PROFILE_PLACEHOLDER__", """
    <div style="background:#fff;min-height:100vh;padding-bottom:60px;">

        <!-- Stats -->
        <div style="background:#f9f9f9;padding:16px 14px 12px;border-bottom:1px solid #e0e0e0;">
            <div style="display:flex;align-items:center;gap:16px;">
                {% if user.avatar_url %}
                    <img src="{{ user.avatar_url }}" style="width:72px;height:72px;border-radius:50%;object-fit:cover;border:2px solid #ccc;flex-shrink:0;">
                {% elif user.avatar_filename %}
                    <img src="{{ url_for('feed.uploaded_file', filename=user.avatar_filename) }}" style="width:72px;height:72px;border-radius:50%;object-fit:cover;border:2px solid #ccc;flex-shrink:0;">
                {% else %}
                    <div style="width:72px;height:72px;border-radius:50%;background:#e0a050;border:2px solid #ccc;display:flex;align-items:center;justify-content:center;font-size:26px;font-weight:700;color:white;flex-shrink:0;">
                        {{ user.username[0].upper() }}
                    </div>
                {% endif %}
                <div style="flex:1;display:flex;justify-content:space-around;text-align:center;">
                    <div><div style="font-size:18px;font-weight:700;color:#222;">{{ posts_count }}</div><div style="font-size:11px;color:#888;">posts</div></div>
                    <a href="?list=followers" style="text-decoration:none;"><div style="font-size:18px;font-weight:700;color:#222;">{{ followers_count }}</div><div style="font-size:11px;color:#888;">followers</div></a>
                    <a href="?list=following" style="text-decoration:none;"><div style="font-size:18px;font-weight:700;color:#222;">{{ following_count }}</div><div style="font-size:11px;color:#888;">following</div></a>
                </div>
            </div>
            <div style="margin-top:10px;font-size:13px;font-weight:700;color:#222;">{{ user.bio or user.username }}</div>

            <!-- Action buttons -->
            <div style="margin-top:10px;display:flex;gap:8px;">
                {% if user.id == current_user.id %}
                    <a href="/edit-profile" style="flex:1;text-align:center;background:linear-gradient(to bottom,#fff,#ebebeb);border:1px solid #ccc;border-radius:3px;padding:7px 0;font-size:12px;font-weight:700;color:#444;text-decoration:none;">EDIT YOUR PROFILE</a>
                {% elif i_block %}
                    <div style="flex:1;text-align:center;background:#fff0f0;border:1px solid #f5c0c0;border-radius:3px;padding:7px 0;font-size:12px;font-weight:700;color:#e74c3c;">Blocked</div>
                    <a href="/unblock/{{ user.username }}" style="flex:1;text-align:center;background:linear-gradient(to bottom,#fff,#ebebeb);border:1px solid #ccc;border-radius:3px;padding:7px 0;font-size:12px;font-weight:700;color:#444;text-decoration:none;">Unblock</a>
                {% else %}
                    {% if current_user.is_following(user) %}
                        <a href="/unfollow/{{ user.username }}" style="flex:1;text-align:center;background:linear-gradient(to bottom,#fff,#ebebeb);border:1px solid #ccc;border-radius:3px;padding:7px 0;font-size:12px;font-weight:700;color:#444;text-decoration:none;">Following</a>
                    {% else %}
                        <a href="/follow/{{ user.username }}" style="flex:1;text-align:center;background:linear-gradient(to bottom,#4f8fc4,#26679c);border:1px solid #1e527d;border-radius:3px;padding:7px 0;font-size:12px;font-weight:700;color:#fff;text-decoration:none;">Follow</a>
                    {% endif %}
                    <a href="/messages/{{ user.id }}" style="flex:1;text-align:center;background:linear-gradient(to bottom,#fff,#ebebeb);border:1px solid #ccc;border-radius:3px;padding:7px 0;font-size:12px;font-weight:700;color:#444;text-decoration:none;">Message</a>
                {% endif %}
            </div>
        </div>

        <!-- Blocked state -->
        {% if i_block or they_block %}
        <div style="padding:50px 20px;text-align:center;color:#aaa;">
            <i class="fa-solid fa-ban" style="font-size:44px;color:#e74c3c;margin-bottom:14px;display:block;"></i>
            <div style="font-size:14px;font-weight:700;color:#555;">
                {% if i_block %}You blocked this user.{% else %}This content is unavailable.{% endif %}
            </div>
        </div>

        {% else %}

        <!-- Followers/Following list -->
        {% if show_list %}
        <div style="background:#f0f0f0;border-bottom:1px solid #ddd;padding:8px 16px;display:flex;justify-content:space-between;align-items:center;">
            <span style="font-size:11px;font-weight:700;color:#666;text-transform:uppercase;">
                {% if show_list == 'followers' %}Followed By{% else %}Following{% endif %}
            </span>
            <a href="{{ url_for('profile.profile_view', username=user.username) }}" style="color:#e44;font-weight:700;font-size:13px;text-decoration:none;">✕</a>
        </div>
        <div style="max-height:200px;overflow-y:auto;background:#fafafa;border-bottom:1px solid #ddd;">
            {% if show_list == 'followers' %}
                {% for f in followers_list %}
                <a href="{{ url_for('profile.profile_view', username=f.username) }}" style="display:flex;align-items:center;gap:10px;padding:10px 16px;border-bottom:1px solid #eee;text-decoration:none;">
                    {% if f.avatar_url %}<img src="{{ f.avatar_url }}" style="width:32px;height:32px;border-radius:50%;object-fit:cover;">
                    {% else %}<div style="width:32px;height:32px;border-radius:50%;background:#c5cae9;display:flex;align-items:center;justify-content:center;font-size:11px;font-weight:700;color:#5c6bc0;">{{ f.username[:2].upper() }}</div>{% endif %}
                    <span style="font-size:13px;font-weight:600;color:#333;">@{{ f.username }}</span>
                </a>
                {% else %}<p style="padding:14px;font-size:12px;text-align:center;color:#aaa;">No followers yet.</p>{% endfor %}
            {% else %}
                {% for f in following_list %}
                <a href="{{ url_for('profile.profile_view', username=f.username) }}" style="display:flex;align-items:center;gap:10px;padding:10px 16px;border-bottom:1px solid #eee;text-decoration:none;">
                    {% if f.avatar_url %}<img src="{{ f.avatar_url }}" style="width:32px;height:32px;border-radius:50%;object-fit:cover;">
                    {% else %}<div style="width:32px;height:32px;border-radius:50%;background:#c5cae9;display:flex;align-items:center;justify-content:center;font-size:11px;font-weight:700;color:#5c6bc0;">{{ f.username[:2].upper() }}</div>{% endif %}
                    <span style="font-size:13px;font-weight:600;color:#333;">@{{ f.username }}</span>
                </a>
                {% else %}<p style="padding:14px;font-size:12px;text-align:center;color:#aaa;">Not following anyone.</p>{% endfor %}
            {% endif %}
        </div>
        {% endif %}

        <!-- Tabs: Posts / Saved (only for own profile) -->
        <div style="display:flex;border-bottom:1px solid #e0e0e0;background:#fff;">
            <a href="?tab=posts" style="flex:1;display:flex;align-items:center;justify-content:center;padding:11px 0;text-decoration:none;
               border-bottom:{% if active_tab_p != 'saved' %}2px solid #3897f0{% else %}2px solid transparent{% endif %};">
                <i class="fa-solid fa-grip" style="font-size:18px;color:{% if active_tab_p != 'saved' %}#3897f0{% else %}#bbb{% endif %};"></i>
            </a>
            {% if user.id == current_user.id %}
            <a href="?tab=saved" style="flex:1;display:flex;align-items:center;justify-content:center;padding:11px 0;text-decoration:none;
               border-bottom:{% if active_tab_p == 'saved' %}2px solid #3897f0{% else %}2px solid transparent{% endif %};">
                <i class="fa-regular fa-bookmark" style="font-size:18px;color:{% if active_tab_p == 'saved' %}#3897f0{% else %}#bbb{% endif %};"></i>
            </a>
            {% endif %}
        </div>

        <!-- Posts grid -->
        {% if active_tab_p != 'saved' %}
        <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:2px;padding:2px;">
            {% for post in user.posts %}
            <div style="aspect-ratio:1;overflow:hidden;background:#ddd;position:relative;">
                <a href="{{ url_for('feed.view_post', post_id=post.id) }}" style="display:block;width:100%;height:100%;">
                    {% if post.image_url %}
                        {% if post.resource_type == 'video' %}
                            <video src="{{ post.image_url }}" style="width:100%;height:100%;object-fit:cover;" muted playsinline></video>
                            <div style="position:absolute;top:4px;left:4px;background:rgba(0,0,0,.5);border-radius:3px;padding:2px 5px;">
                                <i class="fa-solid fa-play" style="font-size:9px;color:white;"></i>
                            </div>
                        {% else %}
                            <img src="{{ post.image_url }}" style="width:100%;height:100%;object-fit:cover;">
                        {% endif %}
                    {% else %}
                        <div style="width:100%;height:100%;display:flex;align-items:center;justify-content:center;font-size:10px;color:#aaa;padding:4px;text-align:center;">{{ post.content[:20] if post.content else '' }}</div>
                    {% endif %}
                </a>
                {% if user.id == current_user.id or current_user.is_admin %}
                <form action="{{ url_for('feed.delete_post', post_id=post.id) }}" method="post"
                      onsubmit="return confirm('Delete this post?')" style="position:absolute;top:4px;right:4px;margin:0;">
                    <button type="submit" style="background:rgba(0,0,0,.6);border:none;cursor:pointer;color:white;width:24px;height:24px;border-radius:4px;display:flex;align-items:center;justify-content:center;">
                        <i class="fa-solid fa-trash" style="font-size:10px;"></i>
                    </button>
                </form>
                {% endif %}
            </div>
            {% else %}
            <div style="grid-column:1/-1;padding:40px;text-align:center;color:#aaa;font-size:13px;">No posts yet.</div>
            {% endfor %}
        </div>

        <!-- Saved grid -->
        {% else %}
        <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:2px;padding:2px;">
            {% for sp in saved_posts %}
            <a href="{{ url_for('feed.view_post', post_id=sp.post.id) }}" style="aspect-ratio:1;display:block;overflow:hidden;background:#ddd;position:relative;">
                {% if sp.post.image_url %}
                    {% if sp.post.resource_type == 'video' %}
                        <video src="{{ sp.post.image_url }}" style="width:100%;height:100%;object-fit:cover;" muted playsinline></video>
                        <div style="position:absolute;top:4px;left:4px;background:rgba(0,0,0,.5);border-radius:3px;padding:2px 5px;">
                            <i class="fa-solid fa-play" style="font-size:9px;color:white;"></i>
                        </div>
                    {% else %}
                        <img src="{{ sp.post.image_url }}" style="width:100%;height:100%;object-fit:cover;">
                    {% endif %}
                {% else %}
                    <div style="width:100%;height:100%;display:flex;align-items:center;justify-content:center;">
                        <i class="fa-regular fa-bookmark" style="font-size:24px;color:#ccc;"></i>
                    </div>
                {% endif %}
            </a>
            {% else %}
            <div style="grid-column:1/-1;padding:40px;text-align:center;color:#aaa;font-size:13px;">
                <i class="fa-regular fa-bookmark" style="font-size:36px;display:block;margin-bottom:10px;"></i>
                No saved posts yet.
            </div>
            {% endfor %}
        </div>
        {% endif %}

        {% endif %}
    </div>
    """), user=user, current_user=current_user, posts_count=posts_count,
         followers_count=followers_count, following_count=following_count,
         followers_list=followers_list, following_list=following_list,
         show_list=show_list, i_block=i_block, they_block=they_block,
         active_tab_p=active_tab_p, saved_posts=saved_posts)


@profile.route("/notifications")
@login_required
def notifications():
    notifs = Notification.query.filter_by(user_id=current_user.id)\
        .order_by(Notification.created_at.desc()).all()
    for n in notifs:
        n.is_read = True
    db.session.commit()

    content_html = """
    <div style="background:#fff;min-height:100vh;padding-bottom:60px;">
        <div style="padding:10px 14px 4px;font-size:11px;font-weight:700;color:#888;text-transform:uppercase;letter-spacing:.05em;border-bottom:1px solid #eee;">Notifications</div>
        {% if notifs %}
        {% for n in notifs %}
        <div style="display:flex;align-items:center;padding:12px 14px;border-bottom:1px solid #f0f0f0;">
            <a href="{{ url_for('profile.profile_view', username=n.actor.username) }}" style="flex-shrink:0;margin-right:12px;">
                {% if n.actor.avatar_url %}
                    <img src="{{ n.actor.avatar_url }}" style="width:42px;height:42px;border-radius:50%;object-fit:cover;border:1px solid #ddd;">
                {% else %}
                    <div style="width:42px;height:42px;border-radius:50%;background:#d0d3d6;display:flex;align-items:center;justify-content:center;font-size:14px;font-weight:700;color:#555;border:1px solid #ccc;">{{ n.actor.username[:2].upper() }}</div>
                {% endif %}
            </a>
            <div style="flex:1;font-size:13px;color:#333;line-height:1.4;">
                <a href="{{ url_for('profile.profile_view', username=n.actor.username) }}" style="font-weight:700;color:#222;text-decoration:none;">{{ n.actor.username }}</a>
                {% if n.notif_type == 'like' %} liked your photo.
                {% elif n.notif_type == 'follow' %} started following you.
                {% elif n.notif_type == 'comment' %} commented on your post.{% endif %}
                <div style="font-size:10px;color:#aaa;margin-top:2px;">{{ n.created_at.strftime('%b %d') }}</div>
            </div>
            {% if n.notif_type in ['like','comment'] and n.post and n.post.image_url %}
                <a href="{{ url_for('feed.view_post', post_id=n.post.id) }}" style="flex-shrink:0;margin-left:10px;">
                    <img src="{{ n.post.image_url }}" style="width:44px;height:44px;object-fit:cover;border-radius:3px;border:1px solid #ddd;">
                </a>
            {% elif n.notif_type == 'follow' %}
                <div style="flex-shrink:0;margin-left:10px;width:44px;height:44px;display:flex;align-items:center;justify-content:center;">
                    <i class="fa-solid fa-user-plus" style="font-size:18px;color:#3897f0;"></i>
                </div>
            {% endif %}
        </div>
        {% endfor %}
        {% else %}
        <div style="padding:40px;text-align:center;color:#aaa;font-size:13px;">
            <i class="fa-regular fa-heart" style="font-size:40px;margin-bottom:12px;display:block;"></i>No notifications yet.
        </div>
        {% endif %}
    </div>
    """
    full_html = get_layout(content_html, active_tab='notifications', title='Activity')
    return render_template_string(full_html, notifs=notifs, current_user=current_user)


@profile.route("/follow/<username>")
@login_required
def follow_user(username):
    user = User.query.filter_by(username=username).first_or_404()
    if user != current_user:
        current_user.follow(user)
        existing = Notification.query.filter_by(user_id=user.id, actor_id=current_user.id, notif_type='follow').first()
        if not existing:
            db.session.add(Notification(user_id=user.id, actor_id=current_user.id, notif_type='follow'))
        db.session.commit()
    return redirect(url_for('profile.profile_view', username=username))


@profile.route("/unfollow/<username>")
@login_required
def unfollow_user(username):
    user = User.query.filter_by(username=username).first_or_404()
    if user != current_user:
        current_user.unfollow(user)
        Notification.query.filter_by(user_id=user.id, actor_id=current_user.id, notif_type='follow').delete()
        db.session.commit()
    return redirect(url_for('profile.profile_view', username=username))


@profile.route("/block/<username>")
@login_required
def block_user(username):
    user = User.query.filter_by(username=username).first_or_404()
    if user.id != current_user.id and not current_user.is_blocking(user):
        db.session.add(Block(blocker_id=current_user.id, blocked_id=user.id))
        current_user.unfollow(user)
        user.unfollow(current_user)
        db.session.commit()
    return redirect(url_for('profile.profile_view', username=username))


@profile.route("/unblock/<username>")
@login_required
def unblock_user(username):
    user = User.query.filter_by(username=username).first_or_404()
    Block.query.filter_by(blocker_id=current_user.id, blocked_id=user.id).delete()
    db.session.commit()
    return redirect(url_for('profile.profile_view', username=username))


@profile.route("/report/<username>", methods=["GET","POST"])
@login_required
def report_user(username):
    user = User.query.filter_by(username=username).first_or_404()
    sent = False
    if request.method == "POST":
        reason = request.form.get("reason","").strip()
        note   = request.form.get("note","").strip()
        if reason:
            r = Report(reporter_id=current_user.id, reported_id=user.id, reason=reason, note=note)
            db.session.add(r)
            subject = f"[Report] @{user.username} — {reason}"
            ticket  = SupportTicket(user_id=current_user.id, subject=subject, status="open")
            db.session.add(ticket); db.session.flush()
            body = f"@{current_user.username} reported @{user.username}\n\nReason: {reason}\n\nNote: {note or 'None'}"
            db.session.add(SupportMessage(ticket_id=ticket.id, sender_id=current_user.id, body=body, is_admin=False))
            db.session.commit()
            sent = True

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
        .opt{display:flex;align-items:center;gap:12px;padding:13px 16px;border-bottom:1px solid #eee;cursor:pointer}
        .opt input[type=radio]{accent-color:#e74c3c}
        .opt label{font-size:13px;color:#333;cursor:pointer;flex:1}
        textarea{width:100%;padding:12px 14px;border:none;border-top:1px solid #eee;font-size:13px;outline:none;font-family:inherit;background:#fafafa;resize:none;height:90px}
        .sbtn{display:block;width:calc(100% - 28px);margin:0 14px 20px;padding:13px;background:linear-gradient(to bottom,#e94560,#c73652);color:white;font-weight:700;font-size:14px;border:none;border-radius:4px;cursor:pointer}
        .success{background:#fff0f0;border:1px solid #f5c0c0;border-radius:6px;padding:20px;margin:14px;text-align:center;color:#e74c3c}
    </style></head><body>
    <div class="hdr">
        <a href="javascript:history.back()"><i class="fa-solid fa-chevron-left"></i></a>
        <span>Report @{{ user.username }}</span>
    </div>
    {% if sent %}
    <div class="success">
        <i class="fa-solid fa-flag" style="font-size:32px;margin-bottom:10px;display:block;"></i>
        <strong>Report submitted.</strong><br>
        <span style="font-size:12px;color:#888;">Our team will review it shortly.</span><br>
        <a href="/user/{{ user.username }}" style="display:inline-block;margin-top:12px;background:#4a8db7;color:white;padding:8px 20px;border-radius:4px;font-size:12px;font-weight:700;text-decoration:none;">Back to Profile</a>
    </div>
    {% else %}
    <div style="padding:12px 14px 6px;font-size:12px;color:#888;">Why are you reporting <strong>@{{ user.username }}</strong>?</div>
    <form method="post">
        <div class="card">
            {% for r in ['Spam or fake account','Harassment or bullying','Hate speech','Nudity or sexual content','Violence or dangerous content','Intellectual property violation','Other'] %}
            <div class="opt">
                <input type="radio" name="reason" id="r{{ loop.index }}" value="{{ r }}" required>
                <label for="r{{ loop.index }}">{{ r }}</label>
            </div>
            {% endfor %}
            <textarea name="note" placeholder="Additional details (optional)..."></textarea>
        </div>
        <button type="submit" class="sbtn"><i class="fa-solid fa-flag" style="margin-right:8px;"></i>Submit Report</button>
    </form>
    {% endif %}
    </body></html>
    """, user=user, sent=sent, current_user=current_user)
