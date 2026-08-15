import os
import subprocess
import sys
from functools import wraps
from pathlib import Path
from flask import Flask, render_template, jsonify, request, redirect, url_for, session, flash
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash, check_password_hash

from html_timetable import parse_timetable_html
from skola_online import SkolaOnlineClient
from settings_store import load_settings, save_settings

load_dotenv()
BASE = Path(__file__).resolve().parent
TEST_HTML = BASE / "test_data" / "BB1A-test.html"
DATA_DIR = BASE / "data"
SECRET_FILE = DATA_DIR / "flask-secret.key"


def _secret_key():
    env = os.environ.get("SECRET_KEY")
    if env:
        return env
    DATA_DIR.mkdir(exist_ok=True)
    if not SECRET_FILE.exists():
        SECRET_FILE.write_bytes(os.urandom(32))
        try: SECRET_FILE.chmod(0o600)
        except OSError: pass
    return SECRET_FILE.read_bytes()

app = Flask(__name__)
app.config["SECRET_KEY"] = _secret_key()


def current_skola_client():
    cfg = load_settings()
    # Kvůli zpětné kompatibilitě funguje i původní .env.
    user = cfg.get("skolaonline_user") or os.environ.get("SKOLAONLINE_USER", "")
    password = cfg.get("skolaonline_password") or os.environ.get("SKOLAONLINE_PASSWORD", "")
    return SkolaOnlineClient(username=user, password=password)


def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        cfg = load_settings()
        if not cfg.get("admin_password_hash"):
            return redirect(url_for("admin_setup"))
        if not session.get("admin_ok"):
            return redirect(url_for("admin_login", next=request.path))
        return fn(*args, **kwargs)
    return wrapper

@app.get("/")
def index():
    return render_template("index.html")

@app.get("/rozvrhy")
def rozvrhy():
    return render_template("classes.html")

@app.get("/instagram")
def instagram():
    return redirect("https://www.instagram.com/sssaskv/", code=302)

@app.get("/skolni-rady")
def skolni_rady():
    return render_template("school_rules.html")

@app.get("/api/classes")
def api_classes():
    try:
        classes = current_skola_client().get_classes()
        return jsonify({"ok": True, "classes": classes})
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc), "classes": [{"name": "BB1A", "value": "BB1A"}]})

@app.get("/rozvrh/<path:class_name>")
def timetable(class_name):
    return render_template("timetable.html", class_name=class_name)

@app.get("/api/timetable/<path:class_name>")
def api_timetable(class_name):
    try:
        data = current_skola_client().get_timetable(class_name)
        return jsonify({"ok": True, **data})
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 502

@app.get("/api/timetable-test/<path:class_name>")
def api_timetable_test(class_name):
    try:
        html_text = TEST_HTML.read_text(encoding="utf-8", errors="replace")
        data = parse_timetable_html(html_text, class_name)
        return jsonify({"ok": True, **data, "test": True})
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500

@app.route("/admin/setup", methods=["GET", "POST"])
def admin_setup():
    cfg = load_settings()
    if cfg.get("admin_password_hash"):
        return redirect(url_for("admin_login"))
    if request.method == "POST":
        p1 = request.form.get("password", "")
        p2 = request.form.get("password2", "")
        if len(p1) < 8:
            flash("Heslo správce musí mít alespoň 8 znaků.", "error")
        elif p1 != p2:
            flash("Hesla se neshodují.", "error")
        else:
            cfg["admin_password_hash"] = generate_password_hash(p1)
            save_settings(cfg)
            session["admin_ok"] = True
            return redirect(url_for("admin"))
    return render_template("admin_setup.html")

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    cfg = load_settings()
    if not cfg.get("admin_password_hash"):
        return redirect(url_for("admin_setup"))
    if request.method == "POST":
        if check_password_hash(cfg["admin_password_hash"], request.form.get("password", "")):
            session["admin_ok"] = True
            return redirect(request.args.get("next") or url_for("admin"))
        flash("Nesprávné heslo správce.", "error")
    return render_template("admin_login.html")

@app.post("/admin/logout")
def admin_logout():
    session.clear()
    return redirect(url_for("admin_login"))

@app.route("/admin", methods=["GET", "POST"])
@admin_required
def admin():
    cfg = load_settings()
    if request.method == "POST":
        action = request.form.get("action")
        if action == "save_skola":
            cfg["skolaonline_user"] = request.form.get("skolaonline_user", "").strip()
            cfg["skolaonline_storage_state"] = None
            new_password = request.form.get("skolaonline_password", "")
            if new_password:
                cfg["skolaonline_password"] = new_password
            save_settings(cfg)
            flash("Účet Školy Online byl uložen.", "ok")
        elif action == "clear_skola":
            cfg["skolaonline_user"] = ""
            cfg["skolaonline_password"] = ""
            cfg["skolaonline_storage_state"] = None
            save_settings(cfg)
            flash("Účet Školy Online byl odstraněn.", "ok")
        return redirect(url_for("admin"))
    profile = BASE / "kiosk_browser_profile"
    return render_template(
        "admin.html",
        cfg=cfg,
        skola_has_password=bool(cfg.get("skolaonline_password") or os.environ.get("SKOLAONLINE_PASSWORD")),
        instagram_profile=profile.exists(),
    )


@app.post("/admin/skola-login")
@admin_required
def admin_skola_login():
    try:
        current_skola_client().login(force=True)
        flash("Škola Online je přihlášena. Session byla uložena do PostgreSQL.", "ok")
    except Exception as exc:
        flash(f"Nepodařilo se přihlásit Školu Online: {exc}", "error")
    return redirect(url_for("admin"))

@app.post("/admin/instagram-login")
@admin_required
def admin_instagram_login():
    # Lokální Linux: otevře samostatné okno pro první přihlášení/2FA.
    # Na hostingu se to nespouští.
    if os.environ.get("RENDER"):
        flash("Na Renderu nelze otevřít interaktivní přihlašovací okno. Instagram nastav na kioskovém Linux PC.", "error")
    else:
        try:
            subprocess.Popen([sys.executable, str(BASE / "instagram_login_linux.py")], cwd=BASE)
            flash("Otevřel jsem přihlašovací okno Instagramu. Přihlas se, dokonči případné ověření a okno zavři.", "ok")
        except Exception as exc:
            flash(f"Nepodařilo se spustit Instagram přihlášení: {exc}", "error")
    return redirect(url_for("admin"))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")), debug=False)