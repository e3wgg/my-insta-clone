import os
from flask import Blueprint, request, redirect, url_for, render_template_string, send_from_directory, Response
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from datetime import datetime, timezone
from extensions import db
from models import Post, Comment, Notification, User, SavedPost
from layout import get_layout

feed = Blueprint('feed', __name__)

ALLOWED_EXTENSIONS = {'png','jpg','jpeg','gif','webp','mp4','mov'}
def allowed_file(f):
    return '.' in f and f.rsplit('.',1)[1].lower() in ALLOWED_EXTENSIONS


@feed.route("/")
@login_required
def feed_view():
    # Filter out posts from blocked users
    blocked_ids = {b.blocked_id for b in current_user.blocking}
    blocker_ids = {b.blocker_id for b in current_user.blocked_by}
    hidden = blocked_ids | blocker_ids
    try:
        from sqlalchemy.orm import joinedload
        q = Post.query.options(joinedload(Post.author), joinedload(Post.likes))
        if hidden:
            q = q.filter(~Post.user_id.in_(hidden))
        posts = q.order_by(Post.created_at.desc()).limit(30).all()
    except Exception:
        posts = Post.query.order_by(Post.created_at.desc()).limit(30).all()

    content_html = """
    <div class="mt-0 space-y-0 pb-20">
        {% for post in posts %}
        <div class="feed-container overflow-hidden bg-white mb-2">
            <div class="flex items-center justify-between px-3 py-2 border-b border-gray-100">
                <div class="flex items-center space-x-2">
                    {% if post.author.avatar_url %}
                        <img src="{{ post.author.avatar_url }}" class="w-8 h-8 rounded-full object-cover border border-gray-300" loading="lazy">
                    {% elif post.author.avatar_filename %}
                        <img src="{{ url_for('feed.uploaded_file', filename=post.author.avatar_filename) }}" class="w-8 h-8 rounded-full object-cover border border-gray-300">
                    {% else %}
                        <div class="w-8 h-8 rounded-full bg-gray-300 flex items-center justify-center text-[11px] font-bold text-gray-600 uppercase border border-gray-300">{{ post.author.username[:2] }}</div>
                    {% endif %}
                    <div>
                        <a href="{{ url_for('profile.profile_view', username=post.author.username) }}" class="font-bold text-xs text-gray-900 block leading-tight">{{ post.author.username }}</a>
                        {% if post.author.bio %}<span class="text-[10px] text-gray-400">{{ post.author.bio }}</span>{% endif %}
                    </div>
                </div>
                <div style="position:relative;flex-shrink:0;">
                    <button onclick="toggleMenu('pmenu_{{ post.id }}')"
                            style="background:none;border:none;cursor:pointer;padding:6px 10px;font-size:18px;color:#aaa;line-height:1;">⋯</button>
                    <div id="pmenu_{{ post.id }}"
                         style="display:none;position:absolute;right:0;top:32px;background:white;border:1px solid #ddd;
                                border-radius:10px;box-shadow:0 6px 20px rgba(0,0,0,.15);min-width:150px;z-index:100;overflow:hidden;">
                        <!-- Save -->
                        <a href="{{ url_for('feed.save_post', post_id=post.id) }}"
                           style="display:flex;align-items:center;gap:10px;padding:13px 16px;font-size:13px;
                                  color:#333;text-decoration:none;border-bottom:1px solid #f5f5f5;">
                            <i class="fa-regular fa-bookmark" style="width:16px;color:#4a8db7;"></i>
                            Save
                        </a>
                        <!-- Delete (only owner or admin) -->
                        {% if post.user_id == current_user.id or current_user.is_admin %}
                        <form method="post" action="{{ url_for('feed.delete_post', post_id=post.id) }}"
                              onsubmit="return confirm('Delete this post?');"
                              style="margin:0;padding:0;">
                            <button type="submit"
                                    style="width:100%;display:flex;align-items:center;gap:10px;padding:13px 16px;
                                           font-size:13px;color:#e74c3c;background:none;border:none;cursor:pointer;">
                                <i class="fa-regular fa-trash-can" style="width:16px;"></i>
                                Delete
                            </button>
                        </form>
                        {% endif %}
                    </div>
                </div>
            </div>
            {% if post.image_url %}
            <a href="{{ url_for('feed.view_post', post_id=post.id) }}" class="block w-full bg-black">
                {% if post.resource_type == 'video' %}
                    <video controls class="w-full" style="max-height:380px;"><source src="{{ post.image_url }}"></video>
                {% else %}
                    <img src="{{ post.image_url }}" class="w-full h-auto object-cover" style="max-height:380px;" loading="lazy">
                {% endif %}
            </a>
            {% endif %}
            <div class="px-3 pt-2 pb-1 bg-white">
                <div class="flex items-center space-x-4 mb-1 text-gray-800" style="font-size:22px;">
                    <a href="{{ url_for('feed.like_post', post_id=post.id) }}">
                        {% if current_user in post.likes %}<i class="fa-solid fa-heart text-red-500"></i>
                        {% else %}<i class="fa-regular fa-heart"></i>{% endif %}
                    </a>
                    <i class="fa-regular fa-comment" style="font-size:20px;"></i>
                </div>
                <div class="text-[12px] font-bold text-gray-900 mb-1">&#9829; {{ post.likes|length }} likes</div>
                {% if post.content %}
                <p class="text-[12px] text-gray-800 leading-snug mb-1">
                    <a href="{{ url_for('profile.profile_view', username=post.author.username) }}" class="font-bold text-gray-900 mr-1">{{ post.author.username }}</a>{{ post.content }}
                </p>
                {% endif %}
                {% if post.comments %}
                <a href="{{ url_for('feed.view_post', post_id=post.id) }}" class="text-[11px] text-gray-400 block mb-1">View all {{ post.comments|length }} comments</a>
                {% for comment in post.comments[-1:] %}
                <div class="text-[11px] text-gray-800"><span class="font-bold mr-1 text-gray-900">{{ comment.author.username }}</span>{{ comment.body }}</div>
                {% endfor %}
                {% endif %}
                <form action="{{ url_for('feed.comment_post', post_id=post.id) }}" method="post" class="mt-2 flex items-center border-t border-gray-100 pt-1.5">
                    <input name="body" placeholder="Add a comment..." autocomplete="off" required class="w-full text-[12px] p-1 focus:outline-none bg-transparent text-gray-700 placeholder-gray-400">
                    <button class="text-[#3897f0] font-bold text-[12px] pl-2 whitespace-nowrap">Post</button>
                </form>
            </div>
        </div>
        {% else %}
        <div class="p-8 text-center text-gray-400 text-xs bg-white border border-gray-200">No posts yet.</div>
        {% endfor %}
    </div>
    <script>
    function toggleMenu(id){
        document.querySelectorAll('[id^="pmenu_"]').forEach(function(m){
            if(m.id!==id) m.style.display='none';
        });
        var el=document.getElementById(id);
        if(el) el.style.display=el.style.display==='none'?'block':'none';
    }
    document.addEventListener('click',function(e){
        if(!e.target.closest('[id^="pmenu_"]') && !e.target.closest('button[onclick]')){
            document.querySelectorAll('[id^="pmenu_"]').forEach(function(m){m.style.display='none';});
        }
    });
    </script>
    """
    full_html = get_layout(content_html, active_tab='home')
    return render_template_string(full_html, posts=posts, current_user=current_user)


@feed.route("/post/<int:post_id>")
@login_required
def view_post(post_id):
    post = Post.query.get_or_404(post_id)
    content_html = """
    <div class="mt-2 px-2 pb-20">
        <div class="mb-2"><a href="javascript:history.back()" class="v5-btn text-xs text-gray-600"><i class="fa-solid fa-chevron-left mr-1"></i> Back</a></div>
        <div class="feed-container overflow-hidden shadow-xs bg-white">
            <div class="flex items-center space-x-2 p-2 border-b border-gray-200 bg-[#fcfcfc]">
                {% if post.author.avatar_filename %}
                    <img src="{{ url_for('feed.uploaded_file', filename=post.author.avatar_filename) }}" class="w-7 h-7 rounded-full object-cover">
                {% else %}
                    <div class="w-7 h-7 rounded-full bg-gray-300 flex items-center justify-center text-[10px] font-bold text-gray-600 uppercase border border-gray-400">{{ post.author.username[:2] }}</div>
                {% endif %}
                <a href="{{ url_for('profile.profile_view', username=post.author.username) }}" class="font-bold text-xs text-gray-800">{{ post.author.username }}</a>
            </div>
            {% if post.image_filename %}
            <div class="w-full bg-[#fafafa]">
                <img src="{{ url_for('feed.uploaded_file', filename=post.image_filename) }}" class="w-full h-auto object-cover">
            </div>
            {% endif %}
            <div class="p-3 bg-white">
                <div class="flex space-x-4 mb-1.5 text-gray-700 text-lg">
                    <a href="{{ url_for('feed.like_post', post_id=post.id) }}">
                        {% if current_user in post.likes %}<i class="fa-solid fa-heart text-red-500"></i>
                        {% else %}<i class="fa-regular fa-heart"></i>{% endif %}
                    </a>
                    {% if post.user_id == current_user.id %}
                    <form action="{{ url_for('feed.delete_post', post_id=post.id) }}" method="post"
                          onsubmit="return confirm('Delete this post?')" style="display:inline;">
                        <button type="submit" style="background:none;border:none;cursor:pointer;color:#e74c3c;font-size:18px;padding:0;">
                            <i class="fa-regular fa-trash-can"></i>
                        </button>
                    </form>
                    {% endif %}
                </div>
                <div class="text-[11px] font-bold text-gray-800 mb-1">{{ post.likes|length }} likes</div>
                {% if post.content %}
                <p class="text-xs text-gray-800"><span class="font-bold mr-1 text-gray-900">{{ post.author.username }}</span>{{ post.content }}</p>
                {% endif %}
                <div class="mt-2 border-t border-gray-100 pt-1.5 space-y-1">
                    {% for comment in post.comments %}
                    <div class="text-[11px] text-gray-800"><span class="font-bold mr-1 text-gray-900">{{ comment.author.username }}</span>{{ comment.body }}</div>
                    {% endfor %}
                </div>
                <form action="{{ url_for('feed.comment_post', post_id=post.id) }}" method="post" class="mt-2 flex items-center border-t border-gray-200 pt-1">
                    <input name="body" placeholder="Add a comment..." autocomplete="off" required class="w-full text-xs p-1 focus:outline-none bg-transparent">
                    <button class="text-[#3897f0] font-bold text-xs pl-2">Post</button>
                </form>
            </div>
        </div>
    </div>
    """
    full_html = get_layout(content_html, active_tab='', title='Photo')
    return render_template_string(full_html, post=post, current_user=current_user)


@feed.route("/create-post", methods=["GET","POST"])
@login_required
def create_post():
    if request.method == "POST":
        content = request.form.get("content","").strip()
        file    = request.files.get("photo")
        image_url = image_public_id = resource_type = None

        if file and file.filename:
            from cloudinary_helper import upload_file
            result = upload_file(file, folder="posts")
            if result:
                image_url       = result["url"]
                image_public_id = result["public_id"]
                resource_type   = result["resource_type"]

        if content or image_url:
            post = Post(content=content, image_url=image_url,
                        image_public_id=image_public_id,
                        resource_type=resource_type or "image",
                        author=current_user)
            db.session.add(post); db.session.commit()
        return redirect(url_for('feed.feed_view'))

    content_html = """
    <div class="p-3 pb-20">
        <div class="bg-white p-4 border border-gray-300 rounded-sm shadow-xs">
            <form method="post" enctype="multipart/form-data" class="space-y-4">
                <div>
                    <label class="block text-[11px] font-bold text-gray-500 mb-1 uppercase">Photo or Video</label>
                    <input type="file" name="photo" accept="image/*,video/*" required class="w-full text-xs">
                </div>
                <div>
                    <label class="block text-[11px] font-bold text-gray-500 mb-1 uppercase">Caption</label>
                    <textarea name="content" rows="3" placeholder="Write a caption..." class="w-full p-2 text-xs bg-gray-50 border border-gray-200 rounded-sm focus:outline-none resize-none"></textarea>
                </div>
                <button class="w-full bg-[#125688] text-white py-2 rounded-sm font-bold text-xs uppercase">Share</button>
            </form>
        </div>
    </div>
    """
    full_html = get_layout(content_html, active_tab='add', title='Share Photo')
    return render_template_string(full_html, current_user=current_user)


@feed.route("/save/<int:post_id>")
@login_required
def save_post(post_id):
    post = Post.query.get_or_404(post_id)
    existing = SavedPost.query.filter_by(user_id=current_user.id, post_id=post_id).first()
    if existing:
        db.session.delete(existing)
        msg = "unsaved"
    else:
        db.session.add(SavedPost(user_id=current_user.id, post_id=post_id))
        msg = "saved"
    db.session.commit()
    return redirect(request.referrer or url_for('feed.view_post', post_id=post_id))


@feed.route("/delete-post/<int:post_id>", methods=["POST"])
@login_required
def delete_post(post_id):
    post = Post.query.get_or_404(post_id)
    if post.user_id != current_user.id and not current_user.is_admin:
        return redirect(url_for('feed.feed_view'))
    owner_username = post.author.username
    # Delete from Cloudinary
    if post.image_public_id:
        try:
            from cloudinary_helper import delete_file
            delete_file(post.image_public_id, post.resource_type or "image")
        except Exception as e:
            print(f"Cloudinary delete error: {e}")
    db.session.delete(post)
    db.session.commit()
    if current_user.is_admin and owner_username != current_user.username:
        return redirect(url_for('profile.profile_view', username=owner_username))
    return redirect(url_for('profile.profile_view', username=current_user.username))


@feed.route("/search")
@login_required
def search():
    q     = request.args.get('q','').strip()
    ftype = request.args.get('type','all')   # all / images / videos / accounts
    users = []
    if q:
        users = User.query.filter(User.username.ilike(f"%{q}%")).all()

    # Posts with media for explore grid
    posts = Post.query.filter(Post.image_url != None).order_by(Post.created_at.desc()).all()
    if ftype == 'images':
        posts = [p for p in posts if p.resource_type != 'video']
    elif ftype == 'videos':
        posts = [p for p in posts if p.resource_type == 'video']

    content_html = """
    <div style="background:#fff;min-height:100vh;padding-bottom:60px;">
        <!-- Search bar -->
        <div style="padding:8px 12px;background:#f5f5f5;border-bottom:1px solid #ddd;position:sticky;top:0;z-index:10;">
            <form method="get" style="display:flex;gap:8px;">
                <input name="q" value="{{ q }}" placeholder="Search accounts..." autocomplete="off"
                       style="flex:1;padding:8px 12px;border:1px solid #ccc;border-radius:20px;font-size:13px;outline:none;">
                <button style="padding:8px 16px;background:#4a8db7;color:white;border:none;border-radius:20px;font-size:13px;font-weight:700;cursor:pointer;">Find</button>
            </form>
        </div>

        <!-- Filter tabs -->
        <div style="display:flex;border-bottom:1px solid #eee;background:#fff;">
            {% for t, label in [('all','All'), ('images','Photos'), ('videos','Videos')] %}
            <a href="?q={{ q }}&type={{ t }}" style="flex:1;text-align:center;padding:10px 0;font-size:12px;font-weight:700;text-decoration:none;
               color:{% if ftype==t %}#4a8db7{% else %}#888{% endif %};
               border-bottom:{% if ftype==t %}2px solid #4a8db7{% else %}none{% endif %};">
               {{ label }}
            </a>
            {% endfor %}
        </div>

        <!-- Account results -->
        {% if q and users %}
        <div style="padding:8px 12px;border-bottom:1px solid #f0f0f0;">
            {% for u in users %}
            <a href="{{ url_for('profile.profile_view', username=u.username) }}"
               style="display:flex;align-items:center;gap:12px;padding:8px 0;text-decoration:none;">
                {% if u.avatar_url %}
                    <img src="{{ u.avatar_url }}" style="width:38px;height:38px;border-radius:50%;object-fit:cover;border:1px solid #ddd;">
                {% else %}
                    <div style="width:38px;height:38px;border-radius:50%;background:#c5cae9;display:flex;align-items:center;justify-content:center;font-size:13px;font-weight:700;color:#5c6bc0;">{{ u.username[:2].upper() }}</div>
                {% endif %}
                <span style="font-size:13px;font-weight:700;color:#222;">@{{ u.username }}</span>
            </a>
            {% endfor %}
        </div>
        {% elif q %}
        <div style="padding:16px;text-align:center;font-size:12px;color:#aaa;">No accounts found for "{{ q }}"</div>
        {% endif %}

        <!-- Media grid -->
        <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:2px;padding:2px;">
            {% for p in posts %}
            <a href="{{ url_for('feed.view_post', post_id=p.id) }}"
               style="aspect-ratio:1;display:block;overflow:hidden;background:#ddd;position:relative;">
                {% if p.resource_type == 'video' %}
                    <video src="{{ p.image_url }}" style="width:100%;height:100%;object-fit:cover;" muted></video>
                    <div style="position:absolute;top:4px;right:4px;background:rgba(0,0,0,.5);border-radius:3px;padding:2px 5px;">
                        <i class="fa-solid fa-play" style="font-size:9px;color:white;"></i>
                    </div>
                {% else %}
                    <img src="{{ p.image_url }}" style="width:100%;height:100%;object-fit:cover;">
                {% endif %}
            </a>
            {% endfor %}
        </div>
    </div>
    """
    full_html = get_layout(content_html, active_tab='search', title='Explore')
    return render_template_string(full_html, users=users, q=q, posts=posts,
                                  ftype=ftype, current_user=current_user)


@feed.route("/like/<int:post_id>")
@login_required
def like_post(post_id):
    post = Post.query.get_or_404(post_id)
    if current_user in post.likes:
        post.likes.remove(current_user)
        Notification.query.filter_by(user_id=post.user_id, actor_id=current_user.id, notif_type='like', post_id=post_id).delete()
    else:
        post.likes.append(current_user)
        if post.user_id != current_user.id:
            if not Notification.query.filter_by(user_id=post.user_id, actor_id=current_user.id, notif_type='like', post_id=post_id).first():
                db.session.add(Notification(user_id=post.user_id, actor_id=current_user.id, notif_type='like', post_id=post_id))
    db.session.commit()
    return redirect(request.referrer or url_for('feed.feed_view'))


@feed.route("/comment/<int:post_id>", methods=["POST"])
@login_required
def comment_post(post_id):
    body = request.form.get("body","").strip()
    if body:
        db.session.add(Comment(body=body, user_id=current_user.id, post_id=post_id))
        db.session.flush()
        post = Post.query.get(post_id)
        if post and post.user_id != current_user.id:
            db.session.add(Notification(user_id=post.user_id, actor_id=current_user.id, notif_type='comment', post_id=post_id))
        db.session.commit()
    return redirect(request.referrer or url_for('feed.feed_view'))


@feed.route("/edit-profile", methods=["GET","POST"])
@login_required
def edit_profile():
    if request.method == "POST":
        bio  = request.form.get("bio","").strip()
        file = request.files.get("avatar")
        if file and file.filename:
            from cloudinary_helper import upload_file, delete_file
            # حذف الصورة القديمة
            if current_user.avatar_public_id:
                delete_file(current_user.avatar_public_id, "image")
            result = upload_file(file, folder="avatars")
            if result:
                current_user.avatar_url       = result["url"]
                current_user.avatar_public_id = result["public_id"]
        current_user.bio = bio
        db.session.commit()
        return redirect(url_for('profile.profile_view', username=current_user.username))

    content_html = """
    <div class="p-3 pb-20">
        <form method="post" enctype="multipart/form-data" class="bg-white p-4 border border-gray-300 space-y-4 rounded-sm">
            <div><label class="block text-[11px] font-bold text-gray-500 mb-1 uppercase">Avatar</label>
            <input type="file" name="avatar" accept="image/*" class="w-full text-xs"></div>
            <div><label class="block text-[11px] font-bold text-gray-500 mb-1 uppercase">Bio</label>
            <textarea name="bio" rows="2" class="w-full p-2 text-xs bg-gray-50 border border-gray-200 rounded-sm focus:outline-none">{{ current_user.bio or '' }}</textarea></div>
            <button class="w-full bg-[#125688] text-white py-1.5 rounded-sm text-xs font-bold uppercase">Save</button>
        </form>
    </div>
    """
    full_html = get_layout(content_html, active_tab='profile', title='Edit Profile')
    return render_template_string(full_html, current_user=current_user)


@feed.route('/uploads/<path:filename>')
def uploaded_file(filename):
    from flask import current_app
    import base64
    fp = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
    if os.path.isfile(fp):
        return send_from_directory(current_app.config['UPLOAD_FOLDER'], filename)
    png = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==')
    return Response(png, mimetype='image/png')