from __future__ import annotations

from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

from html_timetable import parse_timetable_html
from settings_store import load_settings, save_settings

TIMETABLE_URL = "https://aplikace.skolaonline.cz/SOL/App/Rozvrh/KRO003_VypisTridy.aspx"


class SkolaOnlineError(RuntimeError):
    pass


class SkolaOnlineClient:
    """Klient Školy Online přes skutečný Chromium prohlížeč (Playwright).

    Na Renderu běží headless Chromium, session/cookies se ukládají přes
    settings_store do PostgreSQL. Lokálně se použije stejné rozhraní.
    """

    def __init__(self, username: str, password: str):
        self.username = (username or "").strip()
        self.password = password or ""

    @staticmethod
    def _browser(pw):
        return pw.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"],
        )

    @staticmethod
    def _context(browser, state=None):
        kwargs = dict(
            locale="cs-CZ",
            user_agent=(
                "Mozilla/5.0 (X11; Linux x86_64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/127.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1365, "height": 900},
        )
        if state:
            kwargs["storage_state"] = state
        return browser.new_context(**kwargs)

    @staticmethod
    def _body_text(page):
        try:
            return page.locator("body").inner_text(timeout=5000)
        except Exception:
            return ""

    @classmethod
    def _botstopper(cls, page):
        text = cls._body_text(page).casefold()
        return any(x in text for x in ("botstopper", "access denied", "oh noes"))

    @staticmethod
    def _is_timetable(page):
        try:
            return (
                "KRO003_VypisTridy.aspx".casefold() in (page.url or "").casefold()
                and page.locator("select#DDLTrida, select[name='DDLTrida']").count() > 0
            )
        except Exception:
            return False

    def _fill_login(self, page):
        if not self.username or not self.password:
            raise SkolaOnlineError("V administraci nejsou nastavené údaje Školy Online.")

        pwd = page.locator('input[type="password"]')
        if not pwd.count():
            raise SkolaOnlineError(
                "Škola Online nevrátila rozvrh ani rozpoznatelný přihlašovací formulář."
            )

        user = None
        selectors = [
            'input[name*="user" i]',
            'input[id*="user" i]',
            'input[name*="login" i]',
            'input[id*="login" i]',
            'input[name*="jmeno" i]',
            'input[id*="jmeno" i]',
            'input[type="email"]',
            'input[type="text"]',
        ]
        for sel in selectors:
            loc = page.locator(sel)
            if loc.count():
                user = loc.first
                break
        if user is None:
            raise SkolaOnlineError("Nepodařilo se najít pole pro uživatelské jméno.")

        user.fill(self.username)
        pwd.first.fill(self.password)

        for sel in (
            'button:has-text("Přihlásit")',
            'input[type="submit"]',
            'button[type="submit"]',
        ):
            loc = page.locator(sel)
            if loc.count():
                loc.first.click()
                return
        pwd.first.press("Enter")

    def _open_logged_page(self, force_login=False):
        cfg = load_settings()
        saved_state = None if force_login else cfg.get("skolaonline_storage_state")

        pw = sync_playwright().start()
        browser = self._browser(pw)
        context = self._context(browser, saved_state)
        page = context.new_page()

        try:
            page.goto(TIMETABLE_URL, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(2500)

            if self._botstopper(page):
                raise SkolaOnlineError(
                    "BotStopper zablokoval i skutečný Chromium prohlížeč na Renderu."
                )

            if not self._is_timetable(page):
                self._fill_login(page)
                try:
                    page.wait_for_load_state("domcontentloaded", timeout=60000)
                except PlaywrightTimeoutError:
                    pass
                page.wait_for_timeout(3500)

                if self._botstopper(page):
                    raise SkolaOnlineError(
                        "BotStopper zablokoval přihlášení i přes Chromium na Renderu."
                    )

                # Některé přihlášení po POSTu neskončí přímo na KRO003.
                if not self._is_timetable(page):
                    page.goto(TIMETABLE_URL, wait_until="domcontentloaded", timeout=60000)
                    page.wait_for_timeout(1800)

            if not self._is_timetable(page):
                raise SkolaOnlineError(
                    "Přihlášení proběhlo, ale nepodařilo se otevřít stránku rozvrhu KRO003."
                )

            cfg = load_settings()
            cfg["skolaonline_storage_state"] = context.storage_state()
            save_settings(cfg)
            return pw, browser, context, page
        except Exception:
            context.close()
            browser.close()
            pw.stop()
            raise

    def login(self, force=False):
        pw = browser = context = page = None
        try:
            pw, browser, context, page = self._open_logged_page(force_login=force)
        finally:
            if context:
                context.close()
            if browser:
                browser.close()
            if pw:
                pw.stop()

    def get_classes(self):
        pw = browser = context = page = None
        try:
            pw, browser, context, page = self._open_logged_page()
            html = page.content()
            soup = BeautifulSoup(html, "html.parser")
            sel = soup.select_one("select#DDLTrida, select[name='DDLTrida']")
            if sel is None:
                raise SkolaOnlineError("V KRO003 nebyl nalezen seznam tříd DDLTrida.")
            return [
                {"name": o.get_text(" ", strip=True), "value": o.get("value", "")}
                for o in sel.find_all("option")
                if o.get_text(" ", strip=True) and o.get("value")
            ]
        finally:
            if context:
                context.close()
            if browser:
                browser.close()
            if pw:
                pw.stop()

    def get_timetable(self, class_name: str):
        pw = browser = context = page = None
        try:
            pw, browser, context, page = self._open_logged_page()
            select = page.locator("select#DDLTrida, select[name='DDLTrida']").first

            options = select.locator("option").all()
            wanted_value = None
            for opt in options:
                label = (opt.inner_text() or "").strip()
                if label.casefold() == class_name.casefold():
                    wanted_value = opt.get_attribute("value")
                    break

            if not wanted_value:
                raise SkolaOnlineError(f"Třída {class_name} není v nabídce Školy Online.")

            current = select.input_value()
            if current != wanted_value:
                select.select_option(value=wanted_value)
                # ASP.NET onchange/postback může navigovat nebo pouze překreslit stránku.
                try:
                    page.wait_for_load_state("domcontentloaded", timeout=30000)
                except PlaywrightTimeoutError:
                    pass
                page.wait_for_timeout(1800)

                # Pokud samotné select_option nevyvolalo postback, vyvoláme change ručně.
                if select.input_value() != wanted_value:
                    select.evaluate("(el) => el.dispatchEvent(new Event('change', {bubbles:true}))")
                    try:
                        page.wait_for_load_state("domcontentloaded", timeout=30000)
                    except PlaywrightTimeoutError:
                        pass
                    page.wait_for_timeout(1200)

            if self._botstopper(page):
                raise SkolaOnlineError("BotStopper zablokoval načtení vybrané třídy.")

            cfg = load_settings()
            cfg["skolaonline_storage_state"] = context.storage_state()
            save_settings(cfg)

            return parse_timetable_html(page.content(), class_name)
        finally:
            if context:
                context.close()
            if browser:
                browser.close()
            if pw:
                pw.stop()
