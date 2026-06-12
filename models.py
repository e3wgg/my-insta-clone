from datetime import datetime, timezone
from flask_login import UserMixin
from extensions import db

followers = db.Table('followers',
    db.Column('follower_id', db.Integer, db.ForeignKey('user.id')),
    db.Column('followed_id', db.Integer, db.ForeignKey('user.id'))
)

post_likes = db.Table('post_likes',
    db.Column('user_id', db.Integer, db.ForeignKey('user.id')),
    db.Column('post_id', db.Integer, db.ForeignKey('post.id'))
)

class User(UserMixin, db.Model):
    id              = db.Column(db.Integer, primary_key=True)
    username        = db.Column(db.String(50), unique=True, nullable=False)
    password_hash   = db.Column(db.String(255), nullable=False)
    avatar_filename = db.Column(db.String(255), nullable=True)   # legacy
    avatar_url      = db.Column(db.String(500), nullable=True)   # Cloudinary URL
    avatar_public_id= db.Column(db.String(255), nullable=True)   # Cloudinary public_id
    bio             = db.Column(db.String(150), nullable=True)
    email           = db.Column(db.String(150), nullable=True)
    email_verified  = db.Column(db.Boolean, default=False)
    verify_token    = db.Column(db.String(64), nullable=True)
    is_banned       = db.Column(db.Boolean, default=False)
    is_admin        = db.Column(db.Boolean, default=False)
    created_at      = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

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

    def is_blocking(self, user):
        return Block.query.filter_by(blocker_id=self.id, blocked_id=user.id).first() is not None


class Block(db.Model):
    id         = db.Column(db.Integer, primary_key=True)
    blocker_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    blocked_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    blocker    = db.relationship("User", foreign_keys=[blocker_id], backref="blocking")
    blocked    = db.relationship("User", foreign_keys=[blocked_id], backref="blocked_by")


class Post(db.Model):
    id              = db.Column(db.Integer, primary_key=True)
    content         = db.Column(db.Text, nullable=True)
    image_filename  = db.Column(db.String(255), nullable=True)   # legacy
    image_url       = db.Column(db.String(500), nullable=True)   # Cloudinary URL
    image_public_id = db.Column(db.String(255), nullable=True)   # Cloudinary public_id
    resource_type   = db.Column(db.String(10), default="image")  # image / video
    created_at      = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    user_id         = db.Column(db.Integer, db.ForeignKey("user.id"))
    author          = db.relationship("User", backref="posts")
    likes           = db.relationship('User', secondary=post_likes,
                        backref=db.backref('liked_posts', lazy='dynamic'))


class Comment(db.Model):
    id         = db.Column(db.Integer, primary_key=True)
    body       = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    user_id    = db.Column(db.Integer, db.ForeignKey("user.id"))
    post_id    = db.Column(db.Integer, db.ForeignKey("post.id"))
    author     = db.relationship("User", backref="comments")
    post       = db.relationship("Post", backref=db.backref("comments", cascade="all, delete-orphan"))


class Message(db.Model):
    id              = db.Column(db.Integer, primary_key=True)
    sender_id       = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    receiver_id     = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    body            = db.Column(db.Text, nullable=True)
    image_filename  = db.Column(db.String(255), nullable=True)   # legacy
    image_url       = db.Column(db.String(500), nullable=True)   # Cloudinary URL
    image_public_id = db.Column(db.String(255), nullable=True)
    resource_type   = db.Column(db.String(10), default="image")
    is_read         = db.Column(db.Boolean, default=False)
    timestamp       = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    sender          = db.relationship("User", foreign_keys=[sender_id],  backref="sent_messages")
    receiver        = db.relationship("User", foreign_keys=[receiver_id], backref="received_messages")


class Notification(db.Model):
    id         = db.Column(db.Integer, primary_key=True)
    user_id    = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    actor_id   = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    notif_type = db.Column(db.String(20), nullable=False)   # like / follow / comment
    post_id    = db.Column(db.Integer, db.ForeignKey("post.id"), nullable=True)
    is_read    = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    user       = db.relationship("User", foreign_keys=[user_id],  backref="notifications")
    actor      = db.relationship("User", foreign_keys=[actor_id], backref="sent_notifications")
    post       = db.relationship("Post", backref=db.backref("notifications", cascade="all, delete-orphan"))


class SupportTicket(db.Model):
    id         = db.Column(db.Integer, primary_key=True)
    user_id    = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    subject    = db.Column(db.String(200), nullable=False)
    status     = db.Column(db.String(20), default="open")   # open / replied / closed
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    user       = db.relationship("User", backref="tickets")


class SupportMessage(db.Model):
    id         = db.Column(db.Integer, primary_key=True)
    ticket_id  = db.Column(db.Integer, db.ForeignKey("support_ticket.id"), nullable=False)
    sender_id  = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    body       = db.Column(db.Text, nullable=False)
    is_admin   = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    ticket     = db.relationship("SupportTicket", backref=db.backref("messages", cascade="all, delete-orphan"))
    sender     = db.relationship("User", foreign_keys=[sender_id])


class Report(db.Model):
    id           = db.Column(db.Integer, primary_key=True)
    reporter_id  = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    reported_id  = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    reason       = db.Column(db.String(200), nullable=False)
    note         = db.Column(db.Text, nullable=True)
    status       = db.Column(db.String(20), default="pending")  # pending / reviewed / dismissed
    created_at   = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    reporter     = db.relationship("User", foreign_keys=[reporter_id], backref="reports_made")
    reported     = db.relationship("User", foreign_keys=[reported_id], backref="reports_received")


class SavedPost(db.Model):
    id         = db.Column(db.Integer, primary_key=True)
    user_id    = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    post_id    = db.Column(db.Integer, db.ForeignKey("post.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    user       = db.relationship("User", backref="saved_posts")
    post       = db.relationship("Post", backref=db.backref("saves", cascade="all, delete-orphan"))