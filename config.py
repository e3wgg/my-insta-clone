import os
from urllib.parse import quote_plus

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

SECRET_KEY = "instagram_classic_v5_final_pure"

# ── Supabase PostgreSQL ──────────────────────────────────────
DB_USER     = "postgres.ibvquhbdksmkkhnljifz"
DB_PASSWORD = quote_plus("Ah132455&&@@")   # تشفير الرموز الخاصة
DB_HOST     = "aws-1-ap-southeast-1.pooler.supabase.com"
DB_PORT     = "5432"
DB_NAME     = "postgres"

SQLALCHEMY_DATABASE_URI = (
    f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
)
SQLALCHEMY_TRACK_MODIFICATIONS = False
SQLALCHEMY_ENGINE_OPTIONS = {
    "pool_pre_ping": True,
    "pool_recycle": 300,
}

# ── Cloudinary ───────────────────────────────────────────────
CLOUDINARY_CLOUD_NAME = "dvhx9svdt"
CLOUDINARY_API_KEY    = "115236221467596"
CLOUDINARY_API_SECRET = "pltOHx1NWPPIkwAcdsIF57FMAQQ"

# ── Upload ───────────────────────────────────────────────────
UPLOAD_FOLDER      = os.path.join(BASE_DIR, "uploads")
MAX_CONTENT_LENGTH = 16 * 1024 * 1024
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp', 'mp4', 'mov'}

# ── Admin ────────────────────────────────────────────────────
ADMIN_SECRET_PATH  = "almunif"
ADMIN_PASSWORD     = "e3wg911"
ADMIN_IP_WHITELIST = []
MAX_ATTEMPTS       = 5
LOCKOUT_SECS       = 300

# ── SMTP Email ────────────────────────────────────────────────
SMTP_HOST = "mail.gmail.com"       # غيّر لـ SMTP server الخاص بك
SMTP_PORT = 465                   # SSL port
SMTP_USER = "vb.oq911@gmail.com"    # البريد المرسل
SMTP_PASS = "asdyam911"           # ← ضع كلمة سر البريد هنا
SMTP_FROM = "Dewgram <vb.oq911@gmail.com>"
