from pathlib import Path
from playwright.sync_api import sync_playwright

BASE = Path(__file__).resolve().parent
PROFILE = BASE / "kiosk_browser_profile"
IG = "https://www.instagram.com/sssaskv/"

with sync_playwright() as p:
    ctx = p.chromium.launch_persistent_context(
        str(PROFILE), headless=False, viewport=None,
        args=["--start-maximized", "--no-first-run"]
    )
    page = ctx.pages[0] if ctx.pages else ctx.new_page()
    page.goto(IG, wait_until="domcontentloaded", timeout=60000)
    print("Přihlas se do Instagramu, dokonči případné 2FA a potom zavři okno prohlížeče.")
    try:
        while ctx.pages:
            page.wait_for_timeout(1000)
    except Exception:
        pass
    ctx.close()
