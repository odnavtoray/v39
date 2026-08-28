
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, make_response
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from pathlib import Path
import os, uuid, json, secrets, hmac, shutil, mimetypes
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from collections import Counter
import re

app = Flask(__name__)

BASE_DIR = Path(__file__).parent
INSTANCE_DIR = BASE_DIR / "instance"
INSTANCE_DIR.mkdir(parents=True, exist_ok=True)

def _persistent_secret():
    env = os.environ.get("SECRET_KEY", "").strip()
    if env:
        return env
    path = INSTANCE_DIR / ".beta_secret_key"
    if path.exists():
        value = path.read_text(encoding="utf-8").strip()
        if value:
            return value
    value = secrets.token_hex(32)
    path.write_text(value, encoding="utf-8")
    return value

app.config["SECRET_KEY"] = _persistent_secret()
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get(
    "DATABASE_URL", "sqlite:///" + str(INSTANCE_DIR / "odna_druga_beta.db").replace("\\","/")
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["UPLOAD_FOLDER"] = str(BASE_DIR / "static" / "uploads")
app.config["MAX_CONTENT_LENGTH"] = 25 * 1024 * 1024
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = os.environ.get("HTTPS_ENABLED","0") == "1"
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(days=30)
app.config["PREFERRED_URL_SCHEME"] = "https" if app.config["SESSION_COOKIE_SECURE"] else "http"
app.permanent_session_lifetime = timedelta(days=30)
db = SQLAlchemy(app)
Path(app.config["UPLOAD_FOLDER"]).mkdir(parents=True, exist_ok=True)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    phone = db.Column(db.String(255), unique=True, nullable=False)
    show_phone = db.Column(db.Boolean, default=True)
    email = db.Column(db.String(255), unique=True, nullable=True)
    name = db.Column(db.String(80), default="Користувач")
    verified = db.Column(db.Boolean, default=True)
    rating = db.Column(db.Float, default=5.0)
    reviews_count = db.Column(db.Integer, default=0)
    deals_count = db.Column(db.Integer, default=0)
    trusted = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    avatar = db.Column(db.String(255), default="")
    avatar_original = db.Column(db.String(255), default="")
    avatar_x = db.Column(db.Float, default=50.0)
    avatar_y = db.Column(db.Float, default=50.0)
    avatar_zoom = db.Column(db.Float, default=1.0)

class Listing(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(180), nullable=False)
    brand = db.Column(db.String(80), default="")
    model = db.Column(db.String(120), default="")
    size = db.Column(db.String(20), default="")
    side = db.Column(db.String(10), nullable=False)
    condition = db.Column(db.String(40), nullable=False)
    gender = db.Column(db.String(20), default="unisex")
    insole_length = db.Column(db.String(20), default="")
    footwear_type = db.Column(db.String(50), default="")
    delivery = db.Column(db.String(120), default="")
    exchange_side = db.Column(db.String(10), default="")
    exchange_size = db.Column(db.String(20), default="")
    exchange_type = db.Column(db.String(50), default="")
    exchange_other = db.Column(db.String(120), default="")
    kind = db.Column(db.String(20), nullable=False)
    price = db.Column(db.Integer, default=0)
    previous_price = db.Column(db.Integer, default=0)
    city = db.Column(db.String(80), nullable=False)
    description = db.Column(db.Text, default="")
    images_json = db.Column(db.Text, default="[]")
    owner_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    owner = db.relationship("User", backref="listings")

    @property
    def images(self):
        try:
            data = json.loads(self.images_json or "[]")
            return data if data else ["/static/placeholder.svg"]
        except Exception:
            return ["/static/placeholder.svg"]


class UserAuth(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class AdminAccess(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class ListingState(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    listing_id = db.Column(db.Integer, db.ForeignKey("listing.id"), unique=True, nullable=False)
    status = db.Column(db.String(24), default="active")  # active/inactive/sold/given/exchanged
    expires_at = db.Column(db.DateTime, nullable=True)
    closed_at = db.Column(db.DateTime, nullable=True)
    bumped_at = db.Column(db.DateTime, nullable=True)

class Review(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    reviewer_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    target_user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    listing_id = db.Column(db.Integer, db.ForeignKey("listing.id"), nullable=False)
    stars = db.Column(db.Integer, nullable=False)
    text = db.Column(db.Text, default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class UserPresence(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), unique=True, nullable=False)
    last_seen_at = db.Column(db.DateTime, default=datetime.utcnow)

class BlockedUser(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    blocker_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    blocked_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    kind = db.Column(db.String(40), nullable=False)
    text = db.Column(db.String(255), default="")
    url = db.Column(db.String(255), default="")
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class ExchangeOffer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    target_listing_id = db.Column(db.Integer, db.ForeignKey("listing.id"), nullable=False)
    offered_listing_id = db.Column(db.Integer, default=0, nullable=False)  # legacy compatibility
    sender_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    recipient_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    offer_brand = db.Column(db.String(80), default="")
    offer_model = db.Column(db.String(120), default="")
    offer_size = db.Column(db.String(20), default="")
    offer_side = db.Column(db.String(10), default="")
    offer_condition = db.Column(db.String(50), default="")
    offer_description = db.Column(db.String(500), default="")
    images_json = db.Column(db.Text, default="[]")
    note = db.Column(db.String(300), default="")
    status = db.Column(db.String(20), default="pending")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    @property
    def images(self):
        try:
            return json.loads(self.images_json or "[]")
        except Exception:
            return []

class Favorite(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    listing_id = db.Column(db.Integer, db.ForeignKey("listing.id"), nullable=False)

class FavoriteNoticeHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    listing_id = db.Column(db.Integer, db.ForeignKey("listing.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    __table_args__ = (db.UniqueConstraint("user_id", "listing_id", name="uq_favorite_notice_user_listing"),)

class Wanted(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    search_text = db.Column("query", db.String(180), nullable=False)
    side = db.Column(db.String(10), nullable=False)
    size = db.Column(db.String(20), default="")
    max_price = db.Column(db.Integer, default=0)
    footwear_type = db.Column(db.String(50), default="")
    notify = db.Column(db.Boolean, default=True)

class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    listing_id = db.Column(db.Integer, db.ForeignKey("listing.id"), nullable=False)
    sender_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    recipient_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    text = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
class Complaint(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    listing_id = db.Column(db.Integer, db.ForeignKey("listing.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    reason = db.Column(db.String(120), nullable=False)

class Feedback(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    category = db.Column(db.String(40), nullable=False, default="idea")
    text = db.Column(db.Text, nullable=False)

class SearchEvent(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    query = db.Column(db.String(180), default="")
    city = db.Column(db.String(80), default="")
    side = db.Column(db.String(10), default="")
    kind = db.Column(db.String(20), default="")
    results_count = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class SiteEvent(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    event_type = db.Column(db.String(40), nullable=False)
    value = db.Column(db.String(180), default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class VisitorEvent(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    visitor_key = db.Column(db.String(64), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    event_type = db.Column(db.String(40), nullable=False)  # page_view/listing_view
    value = db.Column(db.String(180), default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class ModerationEvent(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    listing_id = db.Column(db.Integer, db.ForeignKey("listing.id"), nullable=True)
    event_type = db.Column(db.String(40), nullable=False)  # duplicate/rate_limit/review
    reason = db.Column(db.String(255), default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class UserSetting(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), unique=True, nullable=False)
    sound_enabled = db.Column(db.Boolean, default=True)

class MessageRead(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    message_id = db.Column(db.Integer, db.ForeignKey("message.id"), nullable=False)


def csrf_token():
    token = session.get("_csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        session["_csrf_token"] = token
    return token

@app.before_request
def csrf_protect():
    if request.method in ("POST","PUT","PATCH","DELETE"):
        expected = session.get("_csrf_token")
        supplied = request.form.get("_csrf_token") or request.headers.get("X-CSRF-Token")
        if not expected or not supplied or not hmac.compare_digest(str(expected), str(supplied)):
            return ("CSRF validation failed", 400)

@app.after_request
def beta_security_headers(response):
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Permissions-Policy", "camera=(self), microphone=(), geolocation=()")
    if os.environ.get("HTTPS_ENABLED","0") == "1":
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    # Conservative CSP for this existing app; inline scripts/styles are still used in v23.
    response.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'self'; img-src 'self' data: blob:; "
        "style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'; "
        "connect-src 'self'; frame-ancestors 'self'; base-uri 'self'; form-action 'self'"
    )
    return response

def current_user():
    uid = session.get("user_id")
    return db.session.get(User, uid) if uid else None

def notify(user_id, kind, text, url=""):
    db.session.add(Notification(user_id=user_id, kind=kind, text=text[:255], url=url[:255]))

def blocked_between(a_id, b_id):
    return BlockedUser.query.filter(
        db.or_(
            db.and_(BlockedUser.blocker_id==a_id, BlockedUser.blocked_id==b_id),
            db.and_(BlockedUser.blocker_id==b_id, BlockedUser.blocked_id==a_id)
        )
    ).first() is not None

def last_seen_text(user):
    p=UserPresence.query.filter_by(user_id=user.id).first()
    if not p or not p.last_seen_at:
        return tr("Нещодавно","Недавно")
    delta=datetime.utcnow()-p.last_seen_at
    if delta.total_seconds()<300:
        return tr("Зараз на сайті","Сейчас на сайте")
    if delta.total_seconds()<3600:
        mins=max(1,int(delta.total_seconds()//60))
        return tr(f"Був(ла) {mins} хв тому",f"Был(а) {mins} мин. назад")
    if delta.total_seconds()<86400:
        hrs=max(1,int(delta.total_seconds()//3600))
        return tr(f"Був(ла) {hrs} год тому",f"Был(а) {hrs} ч. назад")
    return tr("Був(ла) нещодавно","Был(а) недавно")

def tr(uk, ru):
    return ru if session.get("lang","uk") == "ru" else uk

def official_cities():
    """Return official city names bundled with the beta build."""
    try:
        path = Path(__file__).parent / "static" / "ukraine_cities.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        return [str(x.get("name","")).strip() for x in data if str(x.get("name","")).strip()]
    except Exception:
        return []

def city_lookup():
    return {name.casefold(): name for name in official_cities()}

def normalize_city(value):
    value = " ".join((value or "").strip().split())
    if not value:
        return ""
    # Capitalize each word while preserving hyphens reasonably well.
    return " ".join("-".join(part[:1].upper()+part[1:] if part else part for part in word.split("-")) for word in value.split())

def visitor_key():
    key = session.get("visitor_key")
    if not key:
        key = uuid.uuid4().hex
        session["visitor_key"] = key
    return key

def log_visitor_event(event_type, value=""):
    # Do not count static files / internal browser requests here; this helper is called explicitly by pages.
    me = current_user()
    db.session.add(VisitorEvent(visitor_key=visitor_key(),
                                user_id=me.id if me else None,
                                event_type=event_type, value=str(value or "")[:180]))
    db.session.commit()

def image_dhash_file(file_obj):
    """Small perceptual hash: catches identical/resized/re-encoded images. Prototype anti-duplicate."""
    try:
        from PIL import Image
        pos = file_obj.stream.tell()
        file_obj.stream.seek(0)
        im = Image.open(file_obj.stream).convert("L").resize((9,8))
        px = list(im.getdata())
        bits = []
        for y in range(8):
            row = px[y*9:(y+1)*9]
            bits.extend(row[x] > row[x+1] for x in range(8))
        value = 0
        for bit in bits:
            value = (value << 1) | int(bit)
        file_obj.stream.seek(pos)
        return f"{value:016x}"
    except Exception:
        try:
            file_obj.stream.seek(0)
        except Exception:
            pass
        return ""

def image_dhash_path(web_path):
    if not web_path or not web_path.startswith("/static/uploads/"):
        return ""
    try:
        from PIL import Image
        local = Path(__file__).parent / web_path.lstrip("/")
        im = Image.open(local).convert("L").resize((9,8))
        px=list(im.getdata()); value=0
        for y in range(8):
            row=px[y*9:(y+1)*9]
            for x in range(8):
                value=(value<<1)|int(row[x]>row[x+1])
        return f"{value:016x}"
    except Exception:
        return ""

def hamming_hex(a,b):
    try:
        return (int(a,16)^int(b,16)).bit_count()
    except Exception:
        return 999

def duplicate_photo_matches(files, ignore_listing_id=None):
    new_hashes=[image_dhash_file(f) for f in files if f and f.filename]
    new_hashes=[h for h in new_hashes if h]
    if not new_hashes:
        return []
    matches=[]
    for listing in Listing.query.all():
        if ignore_listing_id and listing.id == ignore_listing_id:
            continue
        for img in listing.images:
            old=image_dhash_path(img)
            if not old:
                continue
            for nh in new_hashes:
                # <= 4 bits is intentionally conservative to avoid false positives.
                if hamming_hex(nh,old) <= 4:
                    matches.append((listing, img))
                    break
            if matches and matches[-1][0].id == listing.id:
                break
    return matches

def listing_rate_limited(user):
    # Prevent feed flooding while keeping normal sellers comfortable.
    since=datetime.utcnow()-timedelta(hours=1)
    recent=db.session.query(SiteEvent).filter(
        SiteEvent.user_id==user.id,
        SiteEvent.event_type=="listing_created",
        SiteEvent.created_at>=since
    ).count()
    return recent >= 10


def message_parts(text):
    if text and text.startswith("[img]"):
        return {"image": text[5:], "text": ""}
    return {"image": "", "text": text or ""}

def auth_for(user):
    return UserAuth.query.filter_by(user_id=user.id).first() if user else None

def state_for(listing, create=True):
    state = ListingState.query.filter_by(listing_id=listing.id).first()
    if not state and create:
        state = ListingState(listing_id=listing.id, status="active",
                             expires_at=datetime.utcnow()+timedelta(days=30))
        db.session.add(state)
        db.session.commit()
    if state and state.status == "active" and state.expires_at and state.expires_at < datetime.utcnow():
        state.status = "inactive"
        db.session.commit()
    return state

def is_listing_active(listing):
    s = state_for(listing)
    return bool(s and s.status in ("active","reserved"))

def review_summary(user_id):
    reviews = Review.query.filter_by(target_user_id=user_id).order_by(Review.id.desc()).all()
    avg = round(sum(r.stars for r in reviews)/len(reviews), 1) if reviews else 5.0
    dist = {n: sum(1 for r in reviews if r.stars == n) for n in range(5,0,-1)}
    return reviews, avg, dist

def can_review(reviewer, listing, target_id):
    if not reviewer or reviewer.id == target_id:
        return False
    st = state_for(listing)
    if not st or st.status not in ("sold","given","exchanged"):
        return False
    participant_ids = {listing.owner_id}
    for m in Message.query.filter_by(listing_id=listing.id).all():
        participant_ids.update([m.sender_id, m.recipient_id])
    return reviewer.id in participant_ids and target_id in participant_ids

def admin_user(user):
    if not user:
        return False
    if AdminAccess.query.filter_by(user_id=user.id).first():
        return True
    # Compatibility with older local prototype databases where account #1 was treated as admin.
    return bool(user.id == 1 and user.phone != "+380671234567")

def days_left(state):
    if not state or not state.expires_at:
        return 0
    return max(0, (state.expires_at.date()-datetime.utcnow().date()).days)

def avatar_style(user):
    if not user or not user.avatar:
        return ""
    x = max(0.0, min(100.0, float(user.avatar_x or 50.0)))
    y = max(0.0, min(100.0, float(user.avatar_y or 50.0)))
    zoom = max(1.0, min(3.0, float(user.avatar_zoom or 1.0)))
    return f"--avatar-x:{x}%;--avatar-y:{y}%;--avatar-zoom:{zoom};"

def make_avatar_crop(original_path, x=50.0, y=50.0, zoom=1.0):
    """Create a real square avatar crop so every page shows exactly the saved frame."""
    if not original_path or not original_path.startswith("/static/uploads/"):
        return original_path
    try:
        from PIL import Image, ImageOps
        local = Path(__file__).parent / original_path.lstrip("/")
        if not local.exists():
            return original_path
        im = Image.open(local)
        im = ImageOps.exif_transpose(im).convert("RGB")
        w,h = im.size
        if not w or not h:
            return original_path

        x=max(0.0,min(100.0,float(x or 50.0)))
        y=max(0.0,min(100.0,float(y or 50.0)))
        zoom=max(1.0,min(3.0,float(zoom or 1.0)))

        # Reproduce the browser editor's square cover + zoom + drag mathematically.
        S=1000.0
        base=max(S/w, S/h)
        scale=base*zoom
        dw,dh=w*scale,h*scale
        offx=((x-50.0)/100.0)*S
        offy=((y-50.0)/100.0)*S
        left_display=(dw-S)/2.0-offx
        top_display=(dh-S)/2.0-offy
        sx0=left_display/scale
        sy0=top_display/scale
        sw=S/scale
        sh=S/scale

        # Clamp crop to image; avoid blank edges.
        sx0=max(0.0,min(w-sw,sx0)) if w>=sw else 0.0
        sy0=max(0.0,min(h-sh,sy0)) if h>=sh else 0.0
        sx1=min(float(w),sx0+sw)
        sy1=min(float(h),sy0+sh)
        crop=im.crop((sx0,sy0,sx1,sy1))
        crop=crop.resize((900,900), Image.Resampling.LANCZOS)

        name=f"avatar_crop_{uuid.uuid4().hex}.jpg"
        target=Path(app.config["UPLOAD_FOLDER"])/name
        crop.save(target,"JPEG",quality=95,optimize=True)
        return "/static/uploads/"+name
    except Exception:
        return original_path

def rotate_existing_image(path, degrees):
    try:
        degrees = int(degrees or 0) % 360
    except Exception:
        degrees = 0
    if degrees == 0 or not path.startswith("/static/uploads/"):
        return path
    try:
        from PIL import Image
        local = Path(__file__).parent / path.lstrip("/")
        if local.exists():
            im = Image.open(local)
            im = im.rotate(-degrees, expand=True)
            im.save(local)
    except Exception:
        pass
    return path

@app.context_processor
def inject():
    me = current_user()
    unread = 0
    sound_enabled = True
    if me:
        read_ids = {r.message_id for r in MessageRead.query.filter_by(user_id=me.id).all()}
        unread = sum(1 for m in Message.query.filter_by(recipient_id=me.id).all() if m.id not in read_ids)
        setting = UserSetting.query.filter_by(user_id=me.id).first()
        sound_enabled = setting.sound_enabled if setting else True
    notification_count = Notification.query.filter_by(user_id=me.id, is_read=False).filter(Notification.kind != "message").count() if me else 0
    def kyiv_time(dt):
        if not dt:
           return None
        return dt.replace(tzinfo=ZoneInfo("UTC")).astimezone(ZoneInfo("Europe/Kyiv"))
    return {"kyiv_time": kyiv_time,"me": me, "unread_count": unread, "sound_enabled": sound_enabled,
            "notification_count": notification_count,
            "lang": session.get("lang","uk"), "admin_user": admin_user,
            "message_parts": message_parts, "state_for": state_for, "days_left": days_left,
            "avatar_style": avatar_style, "last_seen_text": last_seen_text,
            "favorite_count": lambda listing_id: Favorite.query.filter_by(listing_id=listing_id).count(),
            "csrf_token": csrf_token}

def save_uploaded_files(files):
    """Validate that uploads are real images, normalize them, and store safe server names."""
    saved = []
    try:
        from PIL import Image, ImageOps
    except Exception:
        return saved

    for f in list(files)[:5]:
        if not f or not f.filename:
            continue
        try:
            # Limit each image independently as well as Flask's total request limit.
            f.stream.seek(0, 2)
            size = f.stream.tell()
            f.stream.seek(0)
            if size <= 0 or size > 10 * 1024 * 1024:
                continue

            im = Image.open(f.stream)
            im.verify()
            f.stream.seek(0)
            im = Image.open(f.stream)
            im = ImageOps.exif_transpose(im)

            # Prevent decompression bombs / absurd dimensions.
            if im.width < 40 or im.height < 40 or im.width * im.height > 40_000_000:
                continue

            # Normalize all user photos to JPEG; strips embedded active/metadata payloads.
            if im.mode not in ("RGB","L"):
                bg = Image.new("RGB", im.size, "white")
                if "A" in im.getbands():
                    bg.paste(im, mask=im.getchannel("A"))
                else:
                    bg.paste(im.convert("RGB"))
                im = bg
            else:
                im = im.convert("RGB")

            # Cap dimensions for beta storage while preserving good viewing quality.
            im.thumbnail((2400, 2400), Image.Resampling.LANCZOS)

            name = f"{uuid.uuid4().hex}.jpg"
            target = Path(app.config["UPLOAD_FOLDER"]) / name
            im.save(target, "JPEG", quality=92, optimize=True)
            saved.append("/static/uploads/" + name)
        except Exception:
            try:
                f.stream.seek(0)
            except Exception:
                pass
            continue
    return saved


def validate_listing_form(form, has_images=True):
    errors = []
    required_text = {
        "title": "назву оголошення",
        "brand": "бренд",
        "model": "модель",
        "size": "розмір",
        "city": "місто",
        "description": "опис",
    }
    for key, label in required_text.items():
        value = (form.get(key) or "").strip()
        if not value:
            errors.append(tr(f"Заповніть {label}.", f"Заполните поле: {label}."))
    description = (form.get("description") or "").strip()
    if description and len(description) < 20:
        errors.append(tr("Опис має містити щонайменше 20 символів.", "Описание должно содержать минимум 20 символов."))
    if len(description) > 500:
        errors.append(tr("Опис може містити максимум 500 символів.", "Описание может содержать максимум 500 символов."))
    if form.get("side") not in ("left","right"):
        errors.append(tr("Оберіть сторону: ліва або права.", "Выберите сторону: левая или правая."))
    if form.get("kind") not in ("sale","exchange","give"):
        errors.append(tr("Оберіть тип оголошення.", "Выберите тип объявления."))
    if not (form.get("condition") or "").strip():
        errors.append(tr("Оберіть стан.", "Выберите состояние."))
    if form.get("kind") == "sale":
        try:
            price = int(form.get("price") or 0)
            if price <= 0:
                errors.append(tr("Для продажу вкажіть ціну більше 0 грн.", "Для продажи укажите цену больше 0 грн."))
        except ValueError:
            errors.append(tr("Вкажіть коректну ціну.", "Укажите корректную цену."))
    if not has_images:
        errors.append(tr("Додайте щонайменше одну фотографію.", "Добавьте минимум одну фотографию."))
    city=(form.get("city") or "").strip()
    if city and city.casefold() not in city_lookup():
        errors.append(tr("Оберіть місто зі списку міст України.",
                         "Выберите город из списка городов Украины."))
    return errors

def listing_matches(w, l):
    score = 0
    hay = f"{l.title} {l.brand} {l.model}".lower()
    words = [x for x in w.search_text.lower().split() if len(x) > 1]
    if words:
        hit = sum(1 for x in words if x in hay)
        score += min(35, int(35 * hit / len(words)))
    if w.side == l.side:
        score += 35
    if w.size and w.size.strip().lower() == (l.size or "").strip().lower():
        score += 25
    if getattr(w, "footwear_type", ""):
        if w.footwear_type.strip().lower() == (getattr(l, "footwear_type", "") or "").strip().lower():
            score += 10
    if not w.max_price or l.price <= w.max_price or l.price == 0:
        score += 5
    return min(100, score)

@app.before_request
def ensure_default_language():
    # v15 intentionally starts in Ukrainian once, even if localhost kept
    # a language cookie from an older test build. After that UA/RU choice persists.
    if session.get("language_build") != "v15":
        session["lang"] = "uk"
        session["language_build"] = "v15"
    elif "lang" not in session:
        session["lang"] = "uk"

@app.before_request
def update_presence():
    uid=session.get("user_id")
    if not uid:
        return
    try:
        p=UserPresence.query.filter_by(user_id=uid).first()
        if not p:
            p=UserPresence(user_id=uid,last_seen_at=datetime.utcnow())
            db.session.add(p)
        elif not p.last_seen_at or datetime.utcnow()-p.last_seen_at>timedelta(minutes=3):
            p.last_seen_at=datetime.utcnow()
        db.session.commit()
    except Exception:
        db.session.rollback()

@app.route("/healthz")
def healthz():
    return jsonify({"status":"ok","version":"beta-v24"}), 200
@app.route("/sitemap.xml")
def sitemap():
    active_listings = (
        Listing.query
        .join(ListingState, ListingState.listing_id == Listing.id)
        .filter(ListingState.status == "active")
        .all()
    )

    urls = ["https://odnadruga.com.ua/"]
    urls += [
        f"https://odnadruga.com.ua/listing/{listing.id}"
        for listing in active_listings
    ]

    url_xml = "\n".join(
        f"    <url><loc>{url}</loc></url>"
        for url in urls
    )

    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
{url_xml}
</urlset>"""

    response = make_response(xml)
    response.headers["Content-Type"] = "application/xml"
    return response
@app.route("/robots.txt")
def robots():
    text = """User-agent: *
Allow: /

Sitemap: https://odnadruga.com.ua/sitemap.xml
"""
    response = make_response(text)
    response.headers["Content-Type"] = "text/plain"
    return response
@app.route("/")
def index():
    log_visitor_event("page_view", "home")
    q = request.args.get("q","").strip()
    city = normalize_city(request.args.get("city",""))
    side = request.args.get("side","all")
    size = request.args.get("size","all").strip()
    kind = request.args.get("kind","all")
    sort = request.args.get("sort","new")
    query = Listing.query
    if q:
        like = f"%{q}%"
        query = query.filter(db.or_(Listing.title.ilike(like), Listing.brand.ilike(like), Listing.model.ilike(like)))
    if city:
        query = query.filter(Listing.city.ilike(f"%{city}%"))
    if side in ("left","right"):
        query = query.filter_by(side=side)
    if size and size != "all":
        query = query.filter_by(size=size)
    if kind in ("sale","exchange","give"):
        query = query.filter_by(kind=kind)
    if sort == "cheap":
        query = query.order_by(Listing.price.asc())
    elif sort == "expensive":
        query = query.order_by(Listing.price.desc())
    else:
        query = query.order_by(Listing.id.desc())
    listings = [l for l in query.all() if is_listing_active(l)]
    if sort == "new":
        listings.sort(key=lambda l: ((state_for(l).bumped_at or datetime.min), l.id), reverse=True)
    listings = listings[:48]
    if q or city or (size and size!="all") or side in ("left","right"):
        me = current_user()
        db.session.add(SearchEvent(user_id=me.id if me else None, query=q, city=city,
                                   side=side, kind=kind, results_count=len(listings)))
        db.session.commit()
    fav_ids = set()
    if current_user():
        fav_ids = {f.listing_id for f in Favorite.query.filter_by(user_id=current_user().id)}
    cities = sorted({l.city for l in Listing.query.all() if l.city and is_listing_active(l)})
    sizes = list({l.size for l in Listing.query.all() if l.size and is_listing_active(l)})
    def size_key(v):
        try: return (0, float(str(v).replace(",", ".")))
        except: return (1, str(v).lower())
    sizes = sorted(sizes, key=size_key)
    return render_template("index.html", listings=listings, fav_ids=fav_ids,
                           q=q, city=city, cities=cities, side=side, size=size, sizes=sizes,
                           kind=kind, sort=sort,
                           total_listings=Listing.query.count(),
                           completed_deals=ListingState.query.filter(ListingState.status.in_(["sold","given","exchanged"])).count())

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email","").strip().lower()
        password = request.form.get("password","")
        remember = request.form.get("remember") == "on"
        user = User.query.filter(db.func.lower(User.email) == email).first()
        auth = auth_for(user)
        if not user or not auth or not check_password_hash(auth.password_hash, password):
            flash(tr("Невірна електронна пошта або пароль.", "Неверная электронная почта или пароль."))
            return redirect(url_for("login"))
        session["user_id"] = user.id
        session.permanent = remember
        return redirect(url_for("index"))
    return render_template("login.html")

@app.route("/register", methods=["GET","POST"])
def register():
    if request.method == "POST":
        email = request.form.get("email","").strip().lower()
        name = request.form.get("name","").strip()
        code = request.form.get("code","").strip()
        password = request.form.get("password","")
        confirm = request.form.get("confirm","")
        if not re.match(r"^[^\s@]+@[^\s@]+\.[^\s@]+$", email):
            flash(tr("Вкажіть коректну електронну пошту.", "Укажите корректную электронную почту.")); return redirect(url_for("register"))
        if code != "1111":
            flash(tr("Невірний код. У Beta використовуйте 1111.", "Неверный код. В Beta используйте 1111.")); return redirect(url_for("register"))
        if len(password) < 6:
            flash(tr("Пароль має містити щонайменше 6 символів.", "Пароль должен содержать минимум 6 символов.")); return redirect(url_for("register"))
        if password != confirm:
            flash(tr("Паролі не збігаються.", "Пароли не совпадают.")); return redirect(url_for("register"))
        if User.query.filter(db.func.lower(User.email) == email).first():
            flash(tr("Обліковий запис з такою поштою вже існує.", "Учётная запись с такой почтой уже существует.")); return redirect(url_for("login"))
        # phone is no longer requested; keep an internal unique placeholder for v23/v25 DB compatibility.
        internal_phone = f"email:{uuid.uuid4().hex}"
        user = User(phone=internal_phone, email=email, name=name or tr("Користувач","Пользователь"), verified=True)
        db.session.add(user); db.session.commit()
        db.session.add(SiteEvent(user_id=user.id, event_type="registration", value=user.name))
        db.session.add(UserAuth(user_id=user.id, password_hash=generate_password_hash(password)))
        db.session.commit()
        if AdminAccess.query.count() == 0:
            db.session.add(AdminAccess(user_id=user.id)); db.session.commit()
        session["user_id"] = user.id; session.permanent = True
        return redirect(url_for("index"))
    return render_template("register.html")

@app.post("/auth/send-code")
def send_code():
    email = request.form.get("email","").strip().lower()
    if not email:
        return jsonify({"ok":False,"message":tr("Вкажіть електронну пошту.","Укажите электронную почту.")}), 400
    # Beta v26: mail provider is not connected yet; the UI exposes the beta code.
    return jsonify({"ok":True,"wait":60,"message":tr("Beta-код: 1111","Beta-код: 1111")})

@app.route("/forgot-password", methods=["GET","POST"])
def forgot_password():
    if request.method == "POST":
        email = request.form.get("email","").strip().lower()
        code = request.form.get("code","").strip()
        password = request.form.get("password","")
        confirm = request.form.get("confirm","")
        user = User.query.filter(db.func.lower(User.email) == email).first()
        if not user:
            flash(tr("Користувача з такою поштою не знайдено.","Пользователь с такой почтой не найден."))
            return redirect(url_for("forgot_password"))
        if code != "1111":
            flash(tr("Невірний код. У Beta використовуйте 1111.","Неверный код. В Beta используйте 1111."))
            return redirect(url_for("forgot_password"))
        if len(password) < 6 or password != confirm:
            flash(tr("Перевірте пароль і повторення пароля.","Проверьте пароль и повтор пароля."))
            return redirect(url_for("forgot_password"))
        auth=auth_for(user)
        if not auth:
            auth=UserAuth(user_id=user.id,password_hash=generate_password_hash(password)); db.session.add(auth)
        else:
            auth.password_hash=generate_password_hash(password)
        db.session.commit()
        flash(tr("Пароль оновлено. Тепер увійдіть.","Пароль обновлён. Теперь войдите."))
        return redirect(url_for("login"))
    return render_template("forgot_password.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))

@app.route("/listing/new", methods=["GET","POST"])
def new_listing():
    me = current_user()
    if not me:
        return redirect(url_for("login"))
    if request.method == "POST":
        files = [f for f in request.files.getlist("images") if f and f.filename]
        if listing_rate_limited(me):
            db.session.add(ModerationEvent(user_id=me.id, event_type="rate_limit",
                                           reason="10+ listing attempts in one hour"))
            db.session.commit()
            flash(tr("Забагато оголошень за короткий час. Спробуйте трохи пізніше.",
                     "Слишком много объявлений за короткое время. Попробуйте немного позже."))
            return render_template("listing_form.html", listing=None), 429
        duplicate_matches = duplicate_photo_matches(files)
        if duplicate_matches:
            same = duplicate_matches[0][0]
            db.session.add(ModerationEvent(user_id=me.id, listing_id=same.id,
                                           event_type="duplicate_photo",
                                           reason=f"Similar photo to listing #{same.id}, owner #{same.owner_id}"))
            db.session.commit()
            flash(tr("Схоже фото вже використовується в іншому оголошенні. Дублі не публікуються.",
                     "Похожее фото уже используется в другом объявлении. Дубли не публикуются."))
            return render_template("listing_form.html", listing=None), 400
        errors = validate_listing_form(request.form, has_images=bool(files))
        if errors:
            for err in errors:
                flash(err)
            return render_template("listing_form.html", listing=None), 400
        saved = save_uploaded_files(files)
        listing = Listing(
            title=request.form.get("title","").strip(),
            brand=request.form.get("brand","").strip(),
            model=request.form.get("model","").strip(),
            size=request.form.get("size","").strip(),
            side=request.form.get("side","left"),
            condition=request.form.get("condition","Добрий"),
            gender=request.form.get("gender","unisex"),
            insole_length=request.form.get("insole_length","").strip(),
            footwear_type=request.form.get("footwear_type","").strip(),
            delivery=",".join(request.form.getlist("delivery")),
            exchange_side=request.form.get("exchange_side","") if request.form.get("kind")=="exchange" else "",
            exchange_size=request.form.get("exchange_size","").strip() if request.form.get("kind")=="exchange" else "",
            exchange_type=request.form.get("exchange_type","").strip() if request.form.get("kind")=="exchange" else "",
            exchange_other=request.form.get("exchange_other","").strip() if request.form.get("kind")=="exchange" else "",
            kind=request.form.get("kind","sale"),
            price=(int(request.form.get("price") or 0) if request.form.get("kind")=="sale" else 0),
            city=city_lookup().get((request.form.get("city","") or "").strip().casefold(), normalize_city(request.form.get("city",""))),
            description=request.form.get("description","").strip(),
            images_json=json.dumps(saved, ensure_ascii=False),
            owner_id=me.id
        )
        db.session.add(listing); db.session.commit()
        db.session.add(ListingState(listing_id=listing.id, status="active", expires_at=datetime.utcnow()+timedelta(days=30)))
        db.session.add(SiteEvent(user_id=me.id, event_type="listing_created", value=str(listing.id)))
        db.session.commit()
        # Notify owners of matching saved searches.
        for w in Wanted.query.filter(Wanted.user_id != me.id, Wanted.notify == True).all():
            try:
                if listing_matches(w, listing) >= 55:
                    notify(w.user_id, "match",
                           tr(f"Знайдено збіг: «{listing.title}»", f"Найдено совпадение: «{listing.title}»"),
                           url_for("listing_detail", listing_id=listing.id))
            except Exception:
                pass
        db.session.commit()
        flash(tr("Оголошення опубліковано", "Объявление опубликовано"))
        return redirect(url_for("listing_detail", listing_id=listing.id))
    return render_template("listing_form.html", listing=None)

@app.route("/listing/<int:listing_id>/edit", methods=["GET","POST"])
def edit_listing(listing_id):
    me = current_user()
    if not me:
        return redirect(url_for("login"))
    listing = Listing.query.get_or_404(listing_id)
    if listing.owner_id != me.id:
        flash(tr("Редагувати може тільки власник оголошення", "Редактировать может только владелец объявления"))
        return redirect(url_for("listing_detail", listing_id=listing.id))
    if request.method == "POST":
        existing_before = listing.images[:]
        new_files = [f for f in request.files.getlist("images") if f and f.filename]
        keep_indices_pre = request.form.getlist("keep_image")
        has_kept = bool(keep_indices_pre) if existing_before else False
        errors = validate_listing_form(request.form, has_images=has_kept or bool(new_files))
        if errors:
            for err in errors:
                flash(err)
            return render_template("listing_form.html", listing=listing), 400
        listing.title = request.form.get("title","").strip()
        listing.brand = request.form.get("brand","").strip()
        listing.model = request.form.get("model","").strip()
        listing.size = request.form.get("size","").strip()
        listing.side = request.form.get("side","left")
        listing.condition = request.form.get("condition","Добрий")
        listing.gender = request.form.get("gender","unisex")
        listing.insole_length = request.form.get("insole_length","").strip()
        listing.footwear_type = request.form.get("footwear_type","").strip()
        listing.delivery = ",".join(request.form.getlist("delivery"))
        listing.exchange_side = request.form.get("exchange_side","") if request.form.get("kind")=="exchange" else ""
        listing.exchange_size = request.form.get("exchange_size","").strip() if request.form.get("kind")=="exchange" else ""
        listing.exchange_type = request.form.get("exchange_type","").strip() if request.form.get("kind")=="exchange" else ""
        listing.exchange_other = request.form.get("exchange_other","").strip() if request.form.get("kind")=="exchange" else ""
        old_price = int(listing.price or 0)
        listing.kind = request.form.get("kind","sale")
        new_price = int(request.form.get("price") or 0) if listing.kind=="sale" else 0
        price_dropped = bool(listing.kind=="sale" and old_price > 0 and new_price > 0 and new_price < old_price)
        if price_dropped:
            listing.previous_price = old_price
        elif listing.kind!="sale" or new_price > old_price:
            listing.previous_price = 0
        # If the price is unchanged, preserve the last visible reduction history.
        listing.price = new_price
        listing.city = city_lookup().get((request.form.get("city","") or "").strip().casefold(), normalize_city(request.form.get("city","")))
        listing.description = request.form.get("description","").strip()

        existing = listing.images[:]
        keep_indices = request.form.getlist("keep_image")
        if keep_indices:
            keep = []
            for idx in keep_indices:
                try:
                    keep.append(existing[int(idx)])
                except Exception:
                    pass
            existing = keep
        for idx, path in enumerate(listing.images[:]):
            if path in existing:
                rotate_existing_image(path, request.form.get(f"rotation_existing_{idx}", "0"))
        main_existing = request.form.get("main_existing")
        if main_existing and existing:
            try:
                chosen = listing.images[int(main_existing)]
                if chosen in existing:
                    existing.remove(chosen)
                    existing.insert(0, chosen)
            except Exception:
                pass

        new_saved = save_uploaded_files(new_files)
        combined = (existing + new_saved)[:5]
        listing.images_json = json.dumps(combined, ensure_ascii=False)
        db.session.commit()
        if price_dropped:
            for fav in Favorite.query.filter_by(listing_id=listing.id).all():
                if fav.user_id == listing.owner_id:
                    continue
                notify(
                    fav.user_id,
                    "price_drop",
                    tr(
                        f"Ціна на «{listing.title}» знижена з {listing.previous_price} до {listing.price} грн.",
                        f"Цена на «{listing.title}» снижена с {listing.previous_price} до {listing.price} грн."
                    ),
                    url_for("listing_detail", listing_id=listing.id)
                )
            db.session.commit()
        flash(tr("Оголошення оновлено", "Объявление обновлено"))
        return redirect(url_for("listing_detail", listing_id=listing.id))
    return render_template("listing_form.html", listing=listing)

@app.route("/listing/<int:listing_id>")
def listing_detail(listing_id):
    listing = Listing.query.get_or_404(listing_id)
    log_visitor_event("listing_view", listing_id)
    is_fav = False
    msgs = []
    me = current_user()
    if me:
        is_fav = Favorite.query.filter_by(user_id=me.id, listing_id=listing.id).first() is not None
        msgs = Message.query.filter_by(listing_id=listing.id).order_by(Message.id.asc()).all()
    st = state_for(listing)
    reviews, rating_avg, rating_dist = review_summary(listing.owner_id)
    can_leave_review = can_review(me, listing, listing.owner_id) if me else False
    review_targets = []
    if me and me.id == listing.owner_id and st.status in ("sold","given","exchanged"):
        ids = set()
        for m in msgs:
            ids.update([m.sender_id, m.recipient_id])
        ids.discard(me.id)
        review_targets = [db.session.get(User, uid) for uid in ids if db.session.get(User, uid)]
    my_exchange_listings=[]
    is_blocked=False
    if me and me.id != listing.owner_id:
        my_exchange_listings=[x for x in Listing.query.filter_by(owner_id=me.id).order_by(Listing.id.desc()).all()
                              if is_listing_active(x)]
        is_blocked=blocked_between(me.id, listing.owner_id)
    return render_template("listing.html", listing=listing, is_fav=is_fav, msgs=msgs,
                           listing_state=st, owner_reviews=reviews, owner_rating=rating_avg,
                           rating_dist=rating_dist, can_leave_review=can_leave_review,
                           review_targets=review_targets, my_exchange_listings=my_exchange_listings,
                           is_blocked=is_blocked)

@app.post("/favorite/<int:listing_id>")
def favorite(listing_id):
    me = current_user()
    if not me:
        return redirect(url_for("login"))

    listing = Listing.query.get_or_404(listing_id)
    f = Favorite.query.filter_by(user_id=me.id, listing_id=listing_id).first()
    added = False

    if f:
        db.session.delete(f)
    else:
        db.session.add(Favorite(user_id=me.id, listing_id=listing_id))
        added = True

        # Notify the seller only on this user's first-ever add of this listing.
        # If the same user removes and adds it again later, do not spam the seller.
        if listing.owner_id != me.id:
            seen_before = FavoriteNoticeHistory.query.filter_by(
                user_id=me.id, listing_id=listing_id
            ).first()
            if not seen_before:
                db.session.add(FavoriteNoticeHistory(user_id=me.id, listing_id=listing_id))
                notify(
                    listing.owner_id,
                    "favorite",
                    tr(
                        f"Ваше оголошення «{listing.title}» додали в обране",
                        f"Ваше объявление «{listing.title}» добавили в избранное"
                    ),
                    url_for("listing_detail", listing_id=listing.id)
                )

    db.session.commit()
    favorites_count = Favorite.query.filter_by(listing_id=listing_id).count()

    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return jsonify({"ok": True, "favorite": added, "favorites_count": favorites_count})
    return redirect(request.referrer or url_for("index"))

@app.post("/message/<int:listing_id>")
def message(listing_id):
    me = current_user()
    if not me:
        return redirect(url_for("login"))
    listing = Listing.query.get_or_404(listing_id)
    if listing.owner_id == me.id:
        return redirect(url_for("listing_detail", listing_id=listing.id))
    if blocked_between(me.id, listing.owner_id):
        flash(tr("Повідомлення недоступні: один із користувачів заблокував іншого.",
                 "Сообщения недоступны: один из пользователей заблокировал другого."))
        return redirect(url_for("listing_detail", listing_id=listing.id))
    text = request.form.get("text","").strip()
    image_file = request.files.get("chat_image")
    camera_file = request.files.get("chat_image_camera")
    chosen = image_file if image_file and image_file.filename else camera_file
    if chosen and chosen.filename:
        saved = save_uploaded_files([chosen])
        if saved:
            db.session.add(Message(listing_id=listing.id, sender_id=me.id,
                                   recipient_id=listing.owner_id, text="[img]"+saved[0]))
    if text:
        db.session.add(Message(listing_id=listing.id, sender_id=me.id,
                               recipient_id=listing.owner_id, text=text))
    if text or (chosen and chosen.filename):
        notify(listing.owner_id, "message",
               tr(f"Нове повідомлення щодо «{listing.title}»", f"Новое сообщение по «{listing.title}»"),
               url_for("chat_conversation", listing_id=listing.id, partner_id=me.id))
    db.session.commit()
    return redirect(url_for("listing_detail", listing_id=listing.id))



@app.route("/chat/<int:listing_id>/<int:partner_id>")
def chat_conversation(listing_id, partner_id):
    me = current_user()
    if not me:
        return redirect(url_for("login"))
    listing = Listing.query.get_or_404(listing_id)
    partner = db.session.get(User, partner_id)
    if not partner or partner.id == me.id:
        return redirect(url_for("messages"))
    if me.id != listing.owner_id and partner.id != listing.owner_id:
        return redirect(url_for("messages"))
    if blocked_between(me.id, partner.id):
        flash(tr("Повідомлення недоступні: один із користувачів заблокував іншого.",
                 "Сообщения недоступны: один из пользователей заблокировал другого."))
        return redirect(url_for("messages"))

    msgs = Message.query.filter(
        Message.listing_id == listing.id,
        db.or_(
            db.and_(Message.sender_id == me.id, Message.recipient_id == partner.id),
            db.and_(Message.sender_id == partner.id, Message.recipient_id == me.id)
        )
    ).order_by(Message.id.asc()).all()

    read_ids = {r.message_id for r in MessageRead.query.filter_by(user_id=me.id).all()}
    for m in msgs:
        if m.recipient_id == me.id and m.id not in read_ids:
            db.session.add(MessageRead(user_id=me.id, message_id=m.id))
    db.session.commit()
    return render_template("chat_conversation.html", listing=listing, partner=partner, msgs=msgs)


@app.post("/chat/<int:listing_id>/<int:partner_id>/send")
def chat_send(listing_id, partner_id):
    me = current_user()
    if not me:
        return redirect(url_for("login"))
    listing = Listing.query.get_or_404(listing_id)
    partner = db.session.get(User, partner_id)
    if not partner or partner.id == me.id:
        return redirect(url_for("messages"))
    if me.id != listing.owner_id and partner.id != listing.owner_id:
        return redirect(url_for("messages"))
    if blocked_between(me.id, partner.id):
        flash(tr("Повідомлення недоступні: один із користувачів заблокував іншого.",
                 "Сообщения недоступны: один из пользователей заблокировал другого."))
        return redirect(url_for("messages"))

    text = request.form.get("text","").strip()
    image_file = request.files.get("chat_image")
    camera_file = request.files.get("chat_image_camera")
    chosen = image_file if image_file and image_file.filename else camera_file
    sent = False

    if chosen and chosen.filename:
        saved = save_uploaded_files([chosen])
        if saved:
            db.session.add(Message(listing_id=listing.id, sender_id=me.id,
                                   recipient_id=partner.id, text="[img]"+saved[0]))
            sent = True
    if text:
        db.session.add(Message(listing_id=listing.id, sender_id=me.id,
                               recipient_id=partner.id, text=text))
        sent = True

    if sent:
        notify(partner.id, "message",
               tr(f"Нове повідомлення щодо «{listing.title}»", f"Новое сообщение по «{listing.title}»"),
               url_for("chat_conversation", listing_id=listing.id, partner_id=me.id))
        db.session.commit()

    return redirect(url_for("chat_conversation", listing_id=listing.id, partner_id=partner.id))


@app.route("/wanted", methods=["GET","POST"])
def wanted():
    me = current_user()
    if not me:
        return redirect(url_for("login"))
    if request.method == "POST":
        db.session.add(Wanted(
            user_id=me.id,
            search_text=request.form.get("query","").strip(),
            side=request.form.get("side","left"),
            size=request.form.get("size","").strip(),
            max_price=int(request.form.get("max_price") or 0),
            footwear_type=request.form.get("footwear_type","").strip(),
            notify=request.form.get("notify") == "on"
        ))
        db.session.commit()
        flash(tr("Пошук збережено. Коли з’явиться відповідне оголошення, система зможе вас повідомити.", "Поиск сохранён. Когда появится подходящее объявление, система сможет вас уведомить."))
        return redirect(url_for("wanted"))

    items = Wanted.query.filter_by(user_id=me.id).order_by(Wanted.id.desc()).all()
    matches = []
    all_listings = [l for l in Listing.query.order_by(Listing.id.desc()).all() if is_listing_active(l)]
    for w in items:
        for l in all_listings:
            if l.owner_id == me.id:
                continue
            score = listing_matches(w, l)
            if score >= 55:
                matches.append({"wanted": w, "listing": l, "score": score})
    matches.sort(key=lambda x: x["score"], reverse=True)
    return render_template("wanted.html", items=items, matches=matches[:12])

@app.post("/wanted/<int:wanted_id>/delete")
def delete_wanted(wanted_id):
    me = current_user()
    if not me:
        return redirect(url_for("login"))
    w = Wanted.query.get_or_404(wanted_id)
    if w.user_id == me.id:
        db.session.delete(w); db.session.commit()
    return redirect(url_for("wanted"))

@app.post("/complaint/<int:listing_id>")
def complaint(listing_id):
    me = current_user()
    if not me:
        return redirect(url_for("login"))
    db.session.add(Complaint(listing_id=listing_id, user_id=me.id,
                             reason=request.form.get("reason","Інше")))
    db.session.commit()
    flash(tr("Скаргу надіслано модератору", "Жалоба отправлена модератору"))
    return redirect(url_for("listing_detail", listing_id=listing_id))

@app.route("/feedback", methods=["GET","POST"])
def feedback():
    me = current_user()
    if request.method == "POST":
        text = request.form.get("text","").strip()
        category = request.form.get("category","idea")
        if not text:
            flash(tr("Напишіть, будь ласка, вашу пропозицію.", "Напишите, пожалуйста, ваше предложение."))
            return redirect(url_for("feedback"))
        db.session.add(Feedback(user_id=me.id if me else None, category=category, text=text))
        db.session.commit()
        flash(tr("Дякуємо! Пропозицію збережено.", "Спасибо! Предложение сохранено."))
        return redirect(url_for("feedback"))
    return render_template("feedback.html")

@app.route("/safety")
def safety():
    return render_template("safety.html")

@app.route("/language/<code>")
def language(code):
    if code in ("uk","ru"):
        session["lang"] = code
        session["language_build"] = "v15"
    return redirect(request.referrer or url_for("index"))

@app.route("/messages")
def messages():
    me = current_user()
    if not me:
        return redirect(url_for("login"))
    msgs = Message.query.filter(
        db.or_(Message.sender_id==me.id, Message.recipient_id==me.id)
    ).order_by(Message.id.desc()).all()

    # Count unread incoming messages separately for the two tabs.
    read_ids = {r.message_id for r in MessageRead.query.filter_by(user_id=me.id).all()}
    buying_unread = 0
    selling_unread = 0
    for m in msgs:
        if m.recipient_id != me.id or m.id in read_ids:
            continue
        listing = db.session.get(Listing, m.listing_id)
        if not listing:
            continue
        if listing.owner_id == me.id:
            selling_unread += 1
        else:
            buying_unread += 1

    buying, selling = [], []
    seen = set()
    for m in msgs:
        listing = db.session.get(Listing, m.listing_id)
        if not listing:
            continue
        partner_id = m.sender_id if m.sender_id != me.id else m.recipient_id
        key = (m.listing_id, partner_id)
        if key in seen:
            continue
        seen.add(key)
        partner = db.session.get(User, partner_id)
        item = {"m": m, "listing": listing, "parts": message_parts(m.text),
                "partner": partner,
                "chat_url": url_for("chat_conversation", listing_id=listing.id, partner_id=partner_id)}
        if listing.owner_id == me.id:
            selling.append(item)
        else:
            buying.append(item)
    return render_template("messages.html", buying=buying, selling=selling,
                           buying_unread=buying_unread, selling_unread=selling_unread)

@app.route("/settings", methods=["GET","POST"])
def settings():
    me = current_user()
    if not me:
        return redirect(url_for("login"))
    setting = UserSetting.query.filter_by(user_id=me.id).first()
    if not setting:
        setting = UserSetting(user_id=me.id, sound_enabled=True)
        db.session.add(setting); db.session.commit()
    if request.method == "POST":
        setting.sound_enabled = request.form.get("sound_enabled") == "on"
        db.session.commit()
        flash(tr("Налаштування збережено", "Настройки сохранены"))
        return redirect(url_for("settings"))
    return render_template("settings.html", setting=setting)

@app.route("/admin/stats")
def admin_stats():
    me=current_user()
    if not admin_user(me):
        flash(tr("Статистика доступна адміністратору","Статистика доступна администратору"))
        return redirect(url_for("profile"))

    period=request.args.get("period","30")
    now=datetime.utcnow()
    if period=="today":
        start=datetime(now.year,now.month,now.day)
    elif period=="7":
        start=now-timedelta(days=7)
    elif period=="30":
        start=now-timedelta(days=30)
    else:
        start=None
        period="all"

    users=User.query.count()
    all_listings=Listing.query.all()
    states=[state_for(l) for l in all_listings]
    listings=len(all_listings)
    active_count=sum(1 for s in states if s.status=="active")
    inactive_count=sum(1 for s in states if s.status=="inactive")
    completed_count=sum(1 for s in states if s.status in ("sold","given","exchanged"))

    search_q=db.session.query(SearchEvent)
    visitor_q=db.session.query(VisitorEvent)
    site_q=db.session.query(SiteEvent)
    moderation_q=db.session.query(ModerationEvent)
    if start:
        search_q=search_q.filter(SearchEvent.created_at>=start)
        visitor_q=visitor_q.filter(VisitorEvent.created_at>=start)
        site_q=site_q.filter(SiteEvent.created_at>=start)
        moderation_q=moderation_q.filter(ModerationEvent.created_at>=start)

    searches=search_q.order_by(db.desc(SearchEvent.created_at),db.desc(SearchEvent.id)).all()
    visitor_events=visitor_q.all()
    site_events=site_q.all()
    moderation_events=moderation_q.all()

    unique_visitors=len({e.visitor_key for e in visitor_events})
    guest_visitors=len({e.visitor_key for e in visitor_events if e.user_id is None})
    registered_visitors=len({e.user_id for e in visitor_events if e.user_id is not None})
    listing_views=sum(1 for e in visitor_events if e.event_type=="listing_view")
    registrations=sum(1 for e in site_events if e.event_type=="registration")
    conversion=round((registrations/guest_visitors*100),1) if guest_visitors else 0

    cities=Counter(l.city for l in all_listings if l.city)
    sizes=Counter(l.size for l in all_listings if l.size)
    sides=Counter(("Ліва" if l.side=="left" else "Права") for l in all_listings)
    kinds=Counter(l.kind for l in all_listings)
    terms,zero=Counter(),Counter()
    for e in searches:
        if e.query:
            key=e.query.strip().lower()
            terms[key]+=1
            if e.results_count==0: zero[key]+=1
    hours=Counter(e.created_at.hour for e in site_events if e.event_type=="listing_created" and e.created_at)
    weekdays=Counter(e.created_at.weekday() for e in site_events if e.event_type=="listing_created" and e.created_at)

    messages_count=Message.query.count()
    favorites_count=Favorite.query.count()
    complaints_count=Complaint.query.count()
    reviews_count=Review.query.count()
    avg_stars=round(db.session.query(db.func.avg(Review.stars)).scalar() or 0,1)
    duplicates=sum(1 for e in moderation_events if e.event_type=="duplicate_photo")
    rate_limits=sum(1 for e in moderation_events if e.event_type=="rate_limit")

    # Listing engagement: at least one message
    listing_ids_with_messages={x[0] for x in db.session.query(Message.listing_id).distinct().all()}
    engaged_listings=len(listing_ids_with_messages)
    deal_rate=round((completed_count/listings*100),1) if listings else 0

    return render_template("admin_stats.html",
        period=period, users=users, listings=listings, active_count=active_count,
        inactive_count=inactive_count, completed_count=completed_count,
        unique_visitors=unique_visitors, guest_visitors=guest_visitors,
        registered_visitors=registered_visitors, listing_views=listing_views,
        registrations=registrations, conversion=conversion,
        searches_count=len(searches), messages_count=messages_count,
        favorites_count=favorites_count, complaints_count=complaints_count,
        reviews_count=reviews_count, avg_stars=avg_stars,
        engaged_listings=engaged_listings, deal_rate=deal_rate,
        duplicates=duplicates, rate_limits=rate_limits,
        top_cities=cities.most_common(10), top_sizes=sizes.most_common(15),
        sides=sides.most_common(), kinds=kinds.most_common(),
        top_terms=terms.most_common(15), zero_terms=zero.most_common(15),
        hours=sorted(hours.items()), weekdays=sorted(weekdays.items()))

@app.post("/listing/<int:listing_id>/renew")
def renew_listing(listing_id):
    me = current_user()
    listing = Listing.query.get_or_404(listing_id)
    if not me or listing.owner_id != me.id:
        return redirect(url_for("login"))
    st = state_for(listing)
    st.status = "active"
    st.expires_at = datetime.utcnow()+timedelta(days=30)
    st.closed_at = None
    db.session.commit()
    flash(tr("Оголошення продовжено ще на 30 днів.","Объявление продлено ещё на 30 дней."))
    return redirect(url_for("profile"))

@app.post("/listing/<int:listing_id>/close")
def close_listing(listing_id):
    me = current_user()
    listing = Listing.query.get_or_404(listing_id)
    if not me or listing.owner_id != me.id:
        return redirect(url_for("login"))
    status = request.form.get("status","inactive")
    if status not in ("sold","given","exchanged","inactive"):
        status = "inactive"
    st = state_for(listing)
    st.status = status
    st.closed_at = datetime.utcnow()
    db.session.add(SiteEvent(user_id=me.id, event_type="listing_closed", value=status))
    if status in ("sold","given","exchanged"):
        me.deals_count = (me.deals_count or 0)+1
    db.session.commit()
    flash(tr("Оголошення перенесено до неактивних.","Объявление перенесено в неактивные."))
    return redirect(url_for("profile"))

@app.post("/listing/<int:listing_id>/reactivate")
def reactivate_listing(listing_id):
    me = current_user()
    listing = Listing.query.get_or_404(listing_id)
    if not me or listing.owner_id != me.id:
        return redirect(url_for("login"))
    st = state_for(listing)
    st.status = "active"
    st.expires_at = datetime.utcnow()+timedelta(days=30)
    st.closed_at = None
    db.session.commit()
    return redirect(url_for("profile"))

@app.post("/listing/<int:listing_id>/delete")
def delete_listing(listing_id):
    me = current_user()
    listing = Listing.query.get_or_404(listing_id)
    if not me or listing.owner_id != me.id:
        return redirect(url_for("login"))
    Favorite.query.filter_by(listing_id=listing.id).delete()
    MessageRead.query.filter(MessageRead.message_id.in_(
        db.session.query(Message.id).filter_by(listing_id=listing.id)
    )).delete(synchronize_session=False)
    Message.query.filter_by(listing_id=listing.id).delete()
    Complaint.query.filter_by(listing_id=listing.id).delete()
    Review.query.filter_by(listing_id=listing.id).delete()
    ListingState.query.filter_by(listing_id=listing.id).delete()
    db.session.delete(listing)
    db.session.commit()
    flash(tr("Оголошення видалено назавжди.","Объявление удалено навсегда."))
    return redirect(url_for("profile"))

@app.route("/user/<int:user_id>")
def public_profile(user_id):
    user = User.query.get_or_404(user_id)
    reviews, rating_avg, rating_dist = review_summary(user.id)
    active_listings = [l for l in Listing.query.filter_by(owner_id=user.id).order_by(Listing.id.desc()).all()
                       if is_listing_active(l)]
    reviewer_map = {r.reviewer_id: db.session.get(User, r.reviewer_id) for r in reviews}
    me=current_user()
    blocked_by_me=bool(me and BlockedUser.query.filter_by(blocker_id=me.id,blocked_id=user.id).first())
    return render_template("public_profile.html", user=user, reviews=reviews,
                           reviewer_map=reviewer_map, rating_avg=rating_avg, rating_dist=rating_dist,
                           active_listings=active_listings, blocked_by_me=blocked_by_me)

@app.post("/review/<int:listing_id>/<int:target_id>")
def add_review(listing_id, target_id):
    me = current_user()
    if not me:
        return redirect(url_for("login"))
    listing = Listing.query.get_or_404(listing_id)
    if not can_review(me, listing, target_id):
        flash(tr("Відгук можна залишити лише після завершеної угоди.","Отзыв можно оставить только после завершённой сделки."))
        return redirect(url_for("listing_detail", listing_id=listing.id))
    existing = Review.query.filter_by(reviewer_id=me.id, target_user_id=target_id, listing_id=listing.id).first()
    if existing:
        flash(tr("Ви вже залишили відгук за цією угодою.","Вы уже оставили отзыв по этой сделке."))
        return redirect(url_for("public_profile", user_id=target_id))
    try:
        stars = max(1, min(5, int(request.form.get("stars","5"))))
    except Exception:
        stars = 5
    text = request.form.get("text","").strip()[:500]
    db.session.add(Review(reviewer_id=me.id, target_user_id=target_id,
                          listing_id=listing.id, stars=stars, text=text))
    notify(target_id, "review", tr("Вам залишили новий відгук.","Вам оставили новый отзыв."),
           url_for("public_profile", user_id=target_id))
    db.session.commit()
    reviews, avg, _ = review_summary(target_id)
    target = db.session.get(User, target_id)
    if target:
        target.rating = avg
        target.reviews_count = len(reviews)
        db.session.commit()
    return redirect(url_for("public_profile", user_id=target_id))

@app.route("/admin/moderation")
def admin_moderation():
    me = current_user()
    if not admin_user(me):
        return redirect(url_for("profile"))
    complaints = Complaint.query.order_by(Complaint.id.desc()).all()
    moderation_events = ModerationEvent.query.order_by(ModerationEvent.id.desc()).limit(100).all()
    return render_template("admin_moderation.html", complaints=complaints, moderation_events=moderation_events)

@app.route("/admin/moderation/chat/<int:listing_id>")
def admin_moderation_chat(listing_id):
    me = current_user()
    if not admin_user(me):
        return redirect(url_for("profile"))
    listing = Listing.query.get_or_404(listing_id)
    # Moderation access is intentionally tied to a complaint on this listing.
    if not Complaint.query.filter_by(listing_id=listing.id).first():
        flash(tr("Доступ до чату відкривається лише для модерації скарги.",
                 "Доступ к чату открывается только для модерации жалобы."))
        return redirect(url_for("admin_moderation"))
    msgs = Message.query.filter_by(listing_id=listing.id).order_by(Message.id.asc()).all()
    db.session.add(SiteEvent(user_id=me.id, event_type="admin_chat_view", value=str(listing.id)))
    db.session.commit()
    return render_template("admin_chat.html", listing=listing, msgs=msgs)


@app.post("/listing/<int:listing_id>/reserve")
def reserve_listing(listing_id):
    me=current_user(); listing=Listing.query.get_or_404(listing_id)
    if not me or listing.owner_id!=me.id: return redirect(url_for("login"))
    st=state_for(listing)
    if st.status=="reserved":
        st.status="active"
        flash(tr("Бронювання скасовано. Оголошення знову активне.","Бронь отменена. Объявление снова активно."))
    else:
        st.status="reserved"
        flash(tr("Оголошення позначено як «Заброньовано».","Объявление отмечено как «Забронировано»."))
    db.session.commit()
    return redirect(request.referrer or url_for("listing_detail", listing_id=listing.id))


@app.post("/user/<int:user_id>/block")
def block_user(user_id):
    me=current_user()
    if not me: return redirect(url_for("login"))
    if me.id==user_id: return redirect(url_for("public_profile",user_id=user_id))
    existing=BlockedUser.query.filter_by(blocker_id=me.id,blocked_id=user_id).first()
    if existing: db.session.delete(existing)
    else: db.session.add(BlockedUser(blocker_id=me.id,blocked_id=user_id))
    db.session.commit()
    return redirect(request.referrer or url_for("public_profile",user_id=user_id))

@app.post("/exchange-offer/<int:target_listing_id>")
def exchange_offer(target_listing_id):
    me=current_user()
    if not me:
        return redirect(url_for("login"))
    target=Listing.query.get_or_404(target_listing_id)
    if target.owner_id==me.id or target.kind!="exchange":
        return redirect(url_for("listing_detail",listing_id=target.id))
    if blocked_between(me.id,target.owner_id):
        flash(tr("Обмін недоступний через блокування користувача.","Обмен недоступен из-за блокировки пользователя."))
        return redirect(url_for("listing_detail",listing_id=target.id))

    brand=(request.form.get("offer_brand") or "").strip()
    model=(request.form.get("offer_model") or "").strip()
    size=(request.form.get("offer_size") or "").strip()
    side=request.form.get("offer_side") or ""
    condition=(request.form.get("offer_condition") or "").strip()
    description=(request.form.get("offer_description") or "").strip()
    note=(request.form.get("note") or "").strip()
    files=[f for f in request.files.getlist("offer_images") if f and f.filename]

    if not brand or not model or not size or side not in ("left","right"):
        flash(tr("Заповніть бренд, модель, розмір і сторону взуття для обміну.",
                 "Заполните бренд, модель, размер и сторону обуви для обмена."))
        return redirect(url_for("listing_detail",listing_id=target.id))
    if not files:
        flash(tr("Додайте хоча б одну фотографію того, що пропонуєте.",
                 "Добавьте хотя бы одну фотографию того, что предлагаете."))
        return redirect(url_for("listing_detail",listing_id=target.id))
    files=files[:5]
    saved=save_uploaded_files(files)

    offer=ExchangeOffer(
        target_listing_id=target.id, offered_listing_id=target.id,
        sender_id=me.id, recipient_id=target.owner_id,
        offer_brand=brand, offer_model=model, offer_size=size, offer_side=side,
        offer_condition=condition, offer_description=description[:500],
        images_json=json.dumps(saved,ensure_ascii=False), note=note[:300]
    )
    db.session.add(offer)
    notify(target.owner_id,"exchange",
           tr(f"Нова пропозиція обміну щодо «{target.title}»",
              f"Новое предложение обмена по «{target.title}»"),
           url_for("exchange_offers"))
    db.session.commit()
    flash(tr("Пропозицію обміну надіслано.","Предложение обмена отправлено."))
    return redirect(url_for("listing_detail",listing_id=target.id))

@app.route("/exchange-offers")
def exchange_offers():
    me=current_user()
    if not me: return redirect(url_for("login"))
    incoming=ExchangeOffer.query.filter_by(recipient_id=me.id).order_by(ExchangeOffer.id.desc()).all()
    outgoing=ExchangeOffer.query.filter_by(sender_id=me.id).order_by(ExchangeOffer.id.desc()).all()
    listing_map={o.target_listing_id: db.session.get(Listing,o.target_listing_id) for o in incoming+outgoing}
    sender_map={o.sender_id: db.session.get(User,o.sender_id) for o in incoming+outgoing}
    return render_template("exchange_offers.html",incoming=incoming,outgoing=outgoing,
                           listing_map=listing_map,sender_map=sender_map)

@app.post("/exchange-offer/<int:offer_id>/<action>")
def exchange_offer_action(offer_id,action):
    me=current_user(); offer=ExchangeOffer.query.get_or_404(offer_id)
    if not me or offer.recipient_id!=me.id: return redirect(url_for("login"))
    if action in ("accepted","declined"):
        offer.status=action
        notify(offer.sender_id,"exchange",
               tr("Відповідь на вашу пропозицію обміну.","Ответ на ваше предложение обмена."),
               url_for("exchange_offers"))
        db.session.commit()
    return redirect(url_for("exchange_offers"))

@app.route("/notifications")
def notifications():
    me=current_user()
    if not me: return redirect(url_for("login"))
    items=Notification.query.filter_by(user_id=me.id).order_by(Notification.id.desc()).limit(100).all()
    for n in items: n.is_read=True
    db.session.commit()
    return render_template("notifications.html",items=items)

@app.route("/account/export")
def export_account():
    me=current_user()
    if not me: return redirect(url_for("login"))
    data={
      "user":{"id":me.id,"name":me.name,"phone":me.phone,"created_at":me.created_at.isoformat() if me.created_at else None},
      "listings":[{"id":l.id,"title":l.title,"city":l.city,"description":l.description} for l in Listing.query.filter_by(owner_id=me.id).all()],
      "wanted":[{"query":w.search_text,"size":w.size,"side":w.side} for w in Wanted.query.filter_by(user_id=me.id).all()],
      "reviews_received":[{"stars":r.stars,"text":r.text} for r in Review.query.filter_by(target_user_id=me.id).all()]
    }
    response=make_response(json.dumps(data,ensure_ascii=False,indent=2))
    response.headers["Content-Type"]="application/json; charset=utf-8"
    response.headers["Content-Disposition"]="attachment; filename=odna-druga-my-data.json"
    return response

@app.post("/account/delete")
def delete_account():
    me=current_user()
    if not me: return redirect(url_for("login"))
    if request.form.get("confirm_text","").strip().upper()!="DELETE":
        flash(tr("Для видалення введіть DELETE.","Для удаления введите DELETE."))
        return redirect(url_for("settings"))
    uid=me.id
    # Keep marketplace history safe by removing dependent private records first, then user's listings.
    for l in Listing.query.filter_by(owner_id=uid).all():
        Favorite.query.filter_by(listing_id=l.id).delete()
        Message.query.filter_by(listing_id=l.id).delete()
        Complaint.query.filter_by(listing_id=l.id).delete()
        Review.query.filter_by(listing_id=l.id).delete()
        ListingState.query.filter_by(listing_id=l.id).delete()
        ExchangeOffer.query.filter(db.or_(ExchangeOffer.target_listing_id==l.id,ExchangeOffer.offered_listing_id==l.id)).delete(synchronize_session=False)
        db.session.delete(l)
    Favorite.query.filter_by(user_id=uid).delete()
    Wanted.query.filter_by(user_id=uid).delete()
    BlockedUser.query.filter(db.or_(BlockedUser.blocker_id==uid,BlockedUser.blocked_id==uid)).delete(synchronize_session=False)
    Notification.query.filter_by(user_id=uid).delete()
    UserPresence.query.filter_by(user_id=uid).delete()
    UserSetting.query.filter_by(user_id=uid).delete()
    UserAuth.query.filter_by(user_id=uid).delete()
    AdminAccess.query.filter_by(user_id=uid).delete()
    Review.query.filter(db.or_(Review.reviewer_id==uid,Review.target_user_id==uid)).delete(synchronize_session=False)
    ExchangeOffer.query.filter(db.or_(ExchangeOffer.sender_id==uid,ExchangeOffer.recipient_id==uid)).delete(synchronize_session=False)
    db.session.delete(me); db.session.commit(); session.clear()
    return redirect(url_for("index"))

@app.route("/profile")
def profile():
    me = current_user()
    if not me:
        return redirect(url_for("login"))
    all_mine = Listing.query.filter_by(owner_id=me.id).order_by(Listing.id.desc()).all()
    active_mine, inactive_mine = [], []
    for l in all_mine:
        st = state_for(l)
        (active_mine if st.status in ("active","reserved") else inactive_mine).append((l, st))
    fav_listings = []
    for f in Favorite.query.filter_by(user_id=me.id).all():
        l = db.session.get(Listing, f.listing_id)
        if l and is_listing_active(l): fav_listings.append(l)
    reviews, rating_avg, rating_dist = review_summary(me.id)
    return render_template("profile.html", active_mine=active_mine, inactive_mine=inactive_mine,
                           fav_listings=fav_listings, reviews=reviews,
                           rating_avg=rating_avg, rating_dist=rating_dist)


@app.post("/profile/name")
def profile_name():
    me=current_user()
    if not me:
        return redirect(url_for("login"))
    name=(request.form.get("name") or "").strip()
    if len(name)<1 or len(name)>10:
        flash(tr("Ім'я має містити від 1 до 10 символів.","Имя должно содержать от 1 до 10 символов."))
        return redirect(url_for("profile"))
    me.name=name
    db.session.commit()
    flash(tr("Ім'я оновлено.","Имя обновлено."))
    return redirect(url_for("profile"))

@app.post("/profile/phone")
def profile_phone():
    me=current_user()
    if not me:
        return redirect(url_for("login"))

    raw=(request.form.get("phone") or "").strip()
    show=request.form.get("show_phone") == "on"

    if not raw:
        # Keep a unique internal placeholder because older beta databases require phone NOT NULL/UNIQUE.
        me.phone=f"email:{uuid.uuid4().hex}"
        me.show_phone=False
        db.session.commit()
        flash(tr("Номер телефону видалено з профілю.","Номер телефона удалён из профиля."))
        return redirect(url_for("profile"))

    # Mobile browsers/phone keyboards may submit spaces, NBSPs, punctuation,
    # directional marks, or a Ukrainian number without the leading +.
    # Normalize from digits only so desktop and iPhone behave identically.
    digits=re.sub(r"\D", "", raw)
    if digits.startswith("00"):
        digits=digits[2:]
    if len(digits)==10 and digits.startswith("0"):
        digits="38"+digits
    elif len(digits)==12 and digits.startswith("380"):
        pass
    compact="+"+digits
    if len(digits)<10 or len(digits)>15:
        flash(tr("Вкажіть коректний номер телефону.","Укажите корректный номер телефона."))
        return redirect(url_for("profile"))

    existing=User.query.filter(User.id != me.id, User.phone == compact).first()
    if existing:
        flash(tr("Цей номер вже використовується іншим акаунтом.","Этот номер уже используется другим аккаунтом."))
        return redirect(url_for("profile"))

    me.phone=compact
    me.show_phone=show
    db.session.commit()
    flash(tr("Телефон у профілі оновлено.","Телефон в профиле обновлён."))
    return redirect(url_for("profile"))

@app.post("/profile/avatar")
def profile_avatar():
    me=current_user()
    if not me:
        return redirect(url_for("login"))
    f=request.files.get("avatar")
    if not f or not f.filename:
        flash(tr("Оберіть фотографію.","Выберите фотографию."))
        return redirect(url_for("profile"))
    saved=save_uploaded_files([f])
    if saved:
        me.avatar_original=saved[0]
        try:
            me.avatar_x=max(0.0,min(100.0,float(request.form.get("avatar_x","50"))))
            me.avatar_y=max(0.0,min(100.0,float(request.form.get("avatar_y","50"))))
            me.avatar_zoom=max(1.0,min(3.0,float(request.form.get("avatar_zoom","1"))))
        except Exception:
            me.avatar_x,me.avatar_y,me.avatar_zoom=50.0,50.0,1.0
        me.avatar=make_avatar_crop(me.avatar_original,me.avatar_x,me.avatar_y,me.avatar_zoom)
        db.session.commit()
        flash(tr("Фото профілю оновлено.","Фото профиля обновлено."))
    return redirect(url_for("profile"))

@app.post("/profile/avatar/settings")
def profile_avatar_settings():
    me=current_user()
    if not me:
        return redirect(url_for("login"))
    if not me.avatar:
        return redirect(url_for("profile"))
    try:
        me.avatar_x=max(0.0,min(100.0,float(request.form.get("avatar_x","50"))))
        me.avatar_y=max(0.0,min(100.0,float(request.form.get("avatar_y","50"))))
        me.avatar_zoom=max(1.0,min(3.0,float(request.form.get("avatar_zoom","1"))))
    except Exception:
        pass
    source=me.avatar_original or me.avatar
    me.avatar_original=source
    me.avatar=make_avatar_crop(source,me.avatar_x,me.avatar_y,me.avatar_zoom)
    db.session.commit()
    flash(tr("Кадрування аватара збережено.","Кадрирование аватара сохранено."))
    return redirect(url_for("profile"))

@app.post("/profile/avatar/delete")
def delete_profile_avatar():
    me=current_user()
    if not me:
        return redirect(url_for("login"))
    me.avatar=""
    me.avatar_original=""
    me.avatar_x=50.0
    me.avatar_y=50.0
    me.avatar_zoom=1.0
    db.session.commit()
    flash(tr("Фото профілю видалено.","Фото профиля удалено."))
    return redirect(url_for("profile"))

@app.route("/api/matches")
def api_matches():
    me = current_user()
    if not me:
        return jsonify([])
    out = []
    for w in Wanted.query.filter_by(user_id=me.id).all():
        for l in [x for x in Listing.query.all() if is_listing_active(x)]:
            if l.owner_id == me.id:
                continue
            score = listing_matches(w, l)
            if score >= 55:
                out.append({"listing_id":l.id,"title":l.title,"score":score})
    return jsonify(sorted(out, key=lambda x:x["score"], reverse=True))

with app.app_context():
    # Lightweight migration for existing local databases.
    try:
        cols = [row[1] for row in db.session.execute(db.text("PRAGMA table_info(user)")).fetchall()]
        if "avatar" not in cols:
            db.session.execute(db.text("ALTER TABLE user ADD COLUMN avatar VARCHAR(255) DEFAULT ''"))
            db.session.commit()
        if "avatar_x" not in cols:
            db.session.execute(db.text("ALTER TABLE user ADD COLUMN avatar_x FLOAT DEFAULT 50"))
        if "avatar_y" not in cols:
            db.session.execute(db.text("ALTER TABLE user ADD COLUMN avatar_y FLOAT DEFAULT 50"))
        if "avatar_zoom" not in cols:
            db.session.execute(db.text("ALTER TABLE user ADD COLUMN avatar_zoom FLOAT DEFAULT 1"))
        db.session.commit()
    except Exception:
        db.session.rollback()
    # v20 fields: keep older local databases compatible.
    try:
        migrations = {
            "user": [("created_at", "DATETIME"), ("avatar_original", "VARCHAR(255) DEFAULT ''"), ("email", "VARCHAR(255)"),
                     ("show_phone", "BOOLEAN DEFAULT 1")],
            "listing": [("gender", "VARCHAR(20) DEFAULT 'unisex'"), ("insole_length", "VARCHAR(20) DEFAULT ''"),
                        ("footwear_type", "VARCHAR(50) DEFAULT ''"), ("delivery", "VARCHAR(120) DEFAULT ''"),
                        ("exchange_side", "VARCHAR(10) DEFAULT ''"), ("exchange_size", "VARCHAR(20) DEFAULT ''"),
                        ("exchange_type", "VARCHAR(50) DEFAULT ''"), ("exchange_other", "VARCHAR(120) DEFAULT ''"),
                        ("previous_price", "INTEGER DEFAULT 0")],
            "wanted": [("footwear_type", "VARCHAR(50) DEFAULT ''")],
            "listing_state": [("bumped_at", "DATETIME")],
            "exchange_offer": [
                ("offer_brand", "VARCHAR(80) DEFAULT ''"),
                ("offer_model", "VARCHAR(120) DEFAULT ''"),
                ("offer_size", "VARCHAR(20) DEFAULT ''"),
                ("offer_side", "VARCHAR(10) DEFAULT ''"),
                ("offer_condition", "VARCHAR(50) DEFAULT ''"),
                ("offer_description", "VARCHAR(500) DEFAULT ''"),
                ("images_json", "TEXT DEFAULT '[]'")
            ]
        }
        for table, fields in migrations.items():
            cols = {row[1] for row in db.session.execute(db.text(f"PRAGMA table_info({table})")).fetchall()}
            for name, sqltype in fields:
                if name not in cols:
                    db.session.execute(db.text(f"ALTER TABLE {table} ADD COLUMN {name} {sqltype}"))
        db.session.commit()
    except Exception:
        db.session.rollback()
    db.create_all()
    try:
        for u in User.query.filter(User.avatar != "").all():
            if not getattr(u,"avatar_original",""):
                source=u.avatar
                u.avatar_original=source
                u.avatar=make_avatar_crop(source,u.avatar_x,u.avatar_y,u.avatar_zoom)
        db.session.commit()
    except Exception:
        db.session.rollback()
    if User.query.count() == 0:
        u = User(phone="+380671234567", email="demo@odna-druga.local", name="Андрій", verified=True, rating=4.9,
                 reviews_count=17, deals_count=23, trusted=True)
        db.session.add(u); db.session.commit()
        demo = [
            ("Nike Air Max 270 — права","Nike","Air Max 270","43","right","Добрий","sale",1200,"Київ"),
            ("Adidas Ultraboost — ліва","Adidas","Ultraboost","43","left","Відмінний","exchange",0,"Львів"),
            ("Puma RS-X — ліва","Puma","RS-X","42","left","Добрий","sale",900,"Харків"),
            ("New Balance 2002R — права","New Balance","2002R","44","right","Відмінний","sale",1300,"Полтава"),
            ("Кросівок Nike — ліва","Nike","Pegasus","41","left","Добрий","give",0,"Вінниця"),
            ("Туфель чоловічий — права","Clarks","Classic","42","right","Гарний","give",0,"Одеса"),
        ]
        for i, x in enumerate(demo):
            imgs = [f"/static/demo-{(i%4)+1}.svg"]
            db.session.add(Listing(title=x[0],brand=x[1],model=x[2],size=x[3],side=x[4],
                                   condition=x[5],kind=x[6],price=x[7],city=x[8],
                                   description="Демо-оголошення для перевірки дизайну та функцій сайту.",
                                   images_json=json.dumps(imgs), owner_id=u.id))
        db.session.commit()

    # Add auth/state records for data created by older prototype versions.
    if AdminAccess.query.count() == 0:
        first_real = User.query.filter(User.phone != "+380671234567").order_by(User.id.asc()).first()
        if first_real:
            db.session.add(AdminAccess(user_id=first_real.id))
            db.session.commit()
    for user in User.query.all():
        if not auth_for(user) and user.phone == "+380671234567":
            db.session.add(UserAuth(user_id=user.id, password_hash=generate_password_hash("demo1234")))
    for listing in Listing.query.all():
        if not ListingState.query.filter_by(listing_id=listing.id).first():
            db.session.add(ListingState(listing_id=listing.id, status="active",
                                        expires_at=datetime.utcnow()+timedelta(days=30)))
    db.session.commit()

if __name__ == "__main__":
    # Local development only. For Beta/Internet use: py serve_beta.py
    debug = os.environ.get("FLASK_DEBUG","0") == "1"
    app.run(host="0.0.0.0", port=5000, debug=debug)
