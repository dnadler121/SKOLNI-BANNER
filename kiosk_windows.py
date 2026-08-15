import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from playwright.sync_api import sync_playwright

BASE = Path(__file__).resolve().parent
LOCAL = "http://127.0.0.1:5000"
IG = "https://www.instagram.com/sssaskv/"
IG_HOST = "www.instagram.com"


def wait_server():
    for _ in range(80):
        try:
            urllib.request.urlopen(LOCAL, timeout=0.5).read(1)
            return
        except Exception:
            time.sleep(0.25)
    raise RuntimeError("Lokální server se nepodařilo spustit.")


def is_allowed_instagram_url(url: str) -> bool:
    clean = url.split("?", 1)[0].split("#", 1)[0].rstrip("/")
    return clean == IG.rstrip("/")


server = subprocess.Popen(
    [sys.executable, str(BASE / "app.py")],
    cwd=BASE,
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL,
)

try:
    wait_server()
    with sync_playwright() as p:
        profile = BASE / "kiosk_browser_profile"
        ctx = p.chromium.launch_persistent_context(
            str(profile),
            channel="chrome",
            headless=False,
            viewport=None,
            args=["--kiosk", "--no-first-run", "--disable-session-crashed-bubble"],
        )
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        state = {"fixing": False}

        # Zabráníme načtení jiné hlavní instagramové stránky ještě před zobrazením.
        def route_guard(route, request):
            try:
                if request.is_navigation_request() and request.frame == page.main_frame:
                    url = request.url
                    if url.startswith("https://www.instagram.com/") and not is_allowed_instagram_url(url):
                        route.abort()
                        if not state["fixing"]:
                            state["fixing"] = True
                            try:
                                page.goto(IG, wait_until="domcontentloaded", timeout=30000)
                            except Exception:
                                pass
                            finally:
                                state["fixing"] = False
                        return
            except Exception:
                pass
            route.continue_()

        ctx.route("**/*", route_guard)

        def protect(pg):
            if state["fixing"] or pg.is_closed():
                return
            url = pg.url
            if url.startswith("https://www.instagram.com/") and not is_allowed_instagram_url(url):
                state["fixing"] = True
                try:
                    pg.goto(IG, wait_until="domcontentloaded", timeout=30000)
                except Exception:
                    pass
                finally:
                    state["fixing"] = False

        def on_new_page(pg):
            # Instagram nesmí otevřít popup / novou kartu.
            if pg != page:
                try:
                    pg.close()
                except Exception:
                    pass

        ctx.on("page", on_new_page)
        page.on("framenavigated", lambda frame: protect(page) if frame == page.main_frame else None)
        page.goto(LOCAL, wait_until="domcontentloaded")

        while not page.is_closed():
            protect(page)
            if page.url.startswith("https://www.instagram.com/"):
                try:
                    # Vlastní návrat na banner. Instagram samotný jinak zůstává nedotčený.
                    page.evaluate(
                        """
                        () => {
                          if (document.getElementById('skolni-banner-back')) return;
                          const b = document.createElement('button');
                          b.id = 'skolni-banner-back';
                          b.textContent = '← ZPĚT NA BANNER';
                          Object.assign(b.style, {
                            position:'fixed', top:'14px', left:'14px', zIndex:'2147483647',
                            padding:'14px 20px', border:'0', borderRadius:'12px',
                            background:'#176b3a', color:'white', fontSize:'18px', fontWeight:'800',
                            boxShadow:'0 3px 12px #0006', cursor:'pointer'
                          });
                          b.onclick = () => location.href='http://127.0.0.1:5000/';
                          document.body.appendChild(b);
                        }
                        """
                    )
                except Exception:
                    pass
            time.sleep(0.20)
        ctx.close()
finally:
    server.terminate()
