import subprocess, sys, time, urllib.request
from pathlib import Path
from playwright.sync_api import sync_playwright

BASE=Path(__file__).resolve().parent
LOCAL="http://127.0.0.1:5000"
IG="https://www.instagram.com/sssaskv/"

def wait_server():
    for _ in range(100):
        try:
            urllib.request.urlopen(LOCAL,timeout=.5).read(1); return
        except Exception: time.sleep(.25)
    raise RuntimeError("Lokální server se nepodařilo spustit.")

def allowed_ig(url):
    clean=url.split("?",1)[0].split("#",1)[0].rstrip("/")
    return clean==IG.rstrip("/")

server=subprocess.Popen([sys.executable,str(BASE/"app.py")],cwd=BASE)
try:
    wait_server()
    with sync_playwright() as p:
        ctx=p.chromium.launch_persistent_context(str(BASE/"kiosk_browser_profile"),headless=False,viewport=None,args=["--kiosk","--no-first-run","--disable-session-crashed-bubble"])
        page=ctx.pages[0] if ctx.pages else ctx.new_page()
        state={"fixing":False}
        def guard(route,request):
            try:
                if request.is_navigation_request() and request.frame==page.main_frame:
                    u=request.url
                    if u.startswith("https://www.instagram.com/") and not allowed_ig(u):
                        route.abort()
                        if not state["fixing"]:
                            state["fixing"]=True
                            try: page.goto(IG,wait_until="domcontentloaded",timeout=30000)
                            except Exception: pass
                            state["fixing"]=False
                        return
                    # z Instagramu nedovolíme přechod na libovolný cizí web.
                    if page.url.startswith("https://www.instagram.com/") and not u.startswith("https://www.instagram.com/") and not u.startswith(LOCAL):
                        route.abort(); return
            except Exception: pass
            route.continue_()
        ctx.route("**/*",guard)
        def protect():
            if state["fixing"] or page.is_closed(): return
            if page.url.startswith("https://www.instagram.com/") and not allowed_ig(page.url):
                state["fixing"]=True
                try: page.goto(IG,wait_until="domcontentloaded",timeout=30000)
                except Exception: pass
                state["fixing"]=False
        def new_page(pg):
            if pg!=page:
                try: pg.close()
                except Exception: pass
        ctx.on("page",new_page)
        page.on("framenavigated",lambda frame: protect() if frame==page.main_frame else None)
        page.goto(LOCAL,wait_until="domcontentloaded")
        while not page.is_closed():
            protect()
            if page.url.startswith("https://www.instagram.com/"):
                try:
                    page.evaluate("""() => {if(document.getElementById('skolni-banner-back'))return;const b=document.createElement('button');b.id='skolni-banner-back';b.textContent='← ZPĚT NA BANNER';Object.assign(b.style,{position:'fixed',top:'14px',left:'14px',zIndex:'2147483647',padding:'14px 20px',border:'0',borderRadius:'12px',background:'#176b3a',color:'white',fontSize:'18px',fontWeight:'800',boxShadow:'0 3px 12px #0006',cursor:'pointer'});b.onclick=()=>location.href='http://127.0.0.1:5000/';document.body.appendChild(b);}""")
                except Exception: pass
            time.sleep(.2)
        ctx.close()
finally:
    server.terminate()
