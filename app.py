import os
from pathlib import Path
from flask import Flask, render_template, jsonify, request, redirect
from dotenv import load_dotenv

from html_timetable import parse_timetable_html
from skola_online import SkolaOnlineClient, SkolaOnlineError
from instagram_feed import InstagramFeed

load_dotenv()
app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "change-me-in-production")
BASE = Path(__file__).resolve().parent
TEST_HTML = BASE / "test_data" / "BB1A-test.html"

instagram_feed = InstagramFeed(BASE, profile_name="sssaskv", limit=40, refresh_seconds=3600)

client = SkolaOnlineClient(
    username=os.environ.get("SKOLAONLINE_USER", ""),
    password=os.environ.get("SKOLAONLINE_PASSWORD", ""),
)

@app.get("/")
def index():
    return render_template("index.html")

@app.get("/rozvrhy")
def rozvrhy():
    return render_template("classes.html")

@app.get("/instagram")
def instagram():
    # v20: Instagram se otevírá přímo v prohlížeči. Kiosk rozšíření na profilu
    # školy povolí pouze posouvání stránky a návrat zpět do banneru.
    return redirect("https://www.instagram.com/sssaskv/", code=302)

@app.get("/api/instagram")
def api_instagram():
    force = request.args.get("refresh") == "1"
    return jsonify({"ok": True, **instagram_feed.get_state(force_refresh=force)})

@app.get("/skolni-rady")
def skolni_rady():
    return render_template("school_rules.html")

@app.get("/api/classes")
def api_classes():
    try:
        classes = client.get_classes()
        return jsonify({"ok": True, "classes": classes})
    except Exception as exc:
        # BB1A ponecháme dostupnou pro test obrazovky i když login selže.
        return jsonify({"ok": False, "error": str(exc), "classes": [{"name": "BB1A", "value": "BB1A"}]})

@app.get("/rozvrh/<path:class_name>")
def timetable(class_name):
    return render_template("timetable.html", class_name=class_name)

@app.get("/api/timetable/<path:class_name>")
def api_timetable(class_name):
    try:
        data = client.get_timetable(class_name)
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

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")), debug=False)
