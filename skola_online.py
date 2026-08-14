from __future__ import annotations

import re
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from html_timetable import parse_timetable_html

TIMETABLE_URL = "https://aplikace.skolaonline.cz/SOL/App/Rozvrh/KRO003_VypisTridy.aspx"


class SkolaOnlineError(RuntimeError):
    pass


class SkolaOnlineClient:
    """Serverový klient bez Playwrightu. Čte přímo HTML KRO003."""

    def __init__(self, username: str, password: str):
        self.username = (username or "").strip()
        self.password = password or ""
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:150.0) Gecko/20100101 Firefox/150.0",
            "Accept-Language": "cs-CZ,cs;q=0.9,en;q=0.7",
        })
        self._logged_in = False

    @staticmethod
    def _is_botstopper(response: requests.Response) -> bool:
        text = response.text[:10000]
        return bool(re.search(r"BotStopper|Access Denied|Oh noes!", text, re.I))

    @staticmethod
    def _is_timetable(response: requests.Response) -> bool:
        return "KRO003_VypisTridy.aspx" in response.url and "CCADynamicCalendarTable" in response.text

    @staticmethod
    def _hidden_fields(form):
        data = {}
        for el in form.select('input[type="hidden"][name]'):
            data[el.get("name")] = el.get("value", "")
        return data

    @staticmethod
    def _find_login_inputs(form):
        inputs = form.find_all("input")
        pass_el = next((x for x in inputs if (x.get("type") or "").lower() == "password" and x.get("name")), None)
        if pass_el is None:
            return None, None
        candidates = []
        for x in inputs:
            if not x.get("name"):
                continue
            typ = (x.get("type") or "text").lower()
            if typ not in ("text", "email"):
                continue
            ident = " ".join((x.get("name", ""), x.get("id", ""), x.get("placeholder", ""))).casefold()
            score = sum(5 for k in ("user", "login", "jmeno", "uživ", "email") if k in ident)
            candidates.append((score, x))
        return (max(candidates, key=lambda p: p[0])[1] if candidates else None), pass_el

    def login(self, force=False):
        if self._logged_in and not force:
            return
        if not self.username or not self.password:
            raise SkolaOnlineError("Nejsou nastavené SKOLAONLINE_USER a SKOLAONLINE_PASSWORD v .env.")

        try:
            r = self.session.get(TIMETABLE_URL, timeout=25, allow_redirects=True)
            r.raise_for_status()
        except requests.RequestException as exc:
            raise SkolaOnlineError(f"Škola Online není dostupná: {exc}") from exc

        if self._is_botstopper(r):
            raise SkolaOnlineError(
                "Škola Online zablokovala serverové přihlášení přes BotStopper. "
                "HTML parser v14 je hotový, ale přihlášení bez prohlížeče tento server momentálně nepovolil."
            )
        if self._is_timetable(r):
            self._logged_in = True
            return

        soup = BeautifulSoup(r.text, "html.parser")
        login_form = user_el = pass_el = None
        for form in soup.find_all("form"):
            u, p = self._find_login_inputs(form)
            if u is not None and p is not None:
                login_form, user_el, pass_el = form, u, p
                break
        if login_form is None:
            raise SkolaOnlineError(
                "Škola Online nevrátila rozvrh ani klasický přihlašovací formulář. "
                f"Konečná URL: {r.url}"
            )

        payload = {}
        for el in login_form.select("input[name]"):
            typ = (el.get("type") or "text").lower()
            if typ in ("submit", "button", "image", "file"):
                continue
            if typ in ("checkbox", "radio") and not el.has_attr("checked"):
                continue
            payload[el["name"]] = el.get("value", "")
        payload[user_el["name"]] = self.username
        payload[pass_el["name"]] = self.password
        submit = login_form.find(["button", "input"], attrs={"type": re.compile("submit", re.I)})
        if submit and submit.get("name"):
            payload[submit["name"]] = submit.get("value", "Přihlásit")

        action = urljoin(r.url, login_form.get("action") or r.url)
        posted = self.session.post(action, data=payload, timeout=25, allow_redirects=True, headers={"Referer": r.url})
        posted.raise_for_status()
        if self._is_botstopper(posted):
            raise SkolaOnlineError("BotStopper zablokoval odeslání přihlašovacího formuláře.")

        test = self.session.get(TIMETABLE_URL, timeout=25, allow_redirects=True)
        test.raise_for_status()
        if not self._is_timetable(test):
            raise SkolaOnlineError(f"Přihlášení nebylo dokončeno. Konečná URL: {test.url}")
        self._logged_in = True

    def _get_page(self):
        self.login()
        r = self.session.get(TIMETABLE_URL, timeout=25, allow_redirects=True)
        r.raise_for_status()
        if not self._is_timetable(r):
            self.login(force=True)
            r = self.session.get(TIMETABLE_URL, timeout=25, allow_redirects=True)
            r.raise_for_status()
        if not self._is_timetable(r):
            raise SkolaOnlineError("Po přihlášení se nepodařilo načíst KRO003 s rozvrhem.")
        return r

    @staticmethod
    def _class_select(soup):
        return soup.select_one("select#DDLTrida, select[name='DDLTrida']")

    def get_classes(self):
        r = self._get_page()
        soup = BeautifulSoup(r.text, "html.parser")
        sel = self._class_select(soup)
        if sel is None:
            raise SkolaOnlineError("V KRO003 nebyl nalezen seznam tříd DDLTrida.")
        return [
            {"name": o.get_text(" ", strip=True), "value": o.get("value", "")}
            for o in sel.find_all("option") if o.get_text(" ", strip=True) and o.get("value")
        ]

    def get_timetable(self, class_name: str):
        r = self._get_page()
        soup = BeautifulSoup(r.text, "html.parser")
        sel = self._class_select(soup)
        if sel is None or not sel.get("name"):
            raise SkolaOnlineError("V KRO003 nebyl nalezen výběr třídy DDLTrida.")

        selected = sel.find("option", selected=True)
        if selected and selected.get_text(" ", strip=True).casefold() == class_name.casefold():
            return parse_timetable_html(r.text, class_name)

        option = next((o for o in sel.find_all("option") if o.get_text(" ", strip=True).casefold() == class_name.casefold()), None)
        if option is None:
            raise SkolaOnlineError(f"Třída {class_name} není v nabídce Školy Online.")

        form = sel.find_parent("form")
        if form is None:
            raise SkolaOnlineError("Výběr třídy není uvnitř ASP.NET formuláře.")

        payload = self._hidden_fields(form)
        # Zachováme aktuálně vybrané hodnoty ostatních selectů.
        for control in form.select("select[name]"):
            current = control.find("option", selected=True)
            if current:
                payload[control["name"]] = current.get("value", "")
        payload[sel["name"]] = option.get("value", "")
        payload["__EVENTTARGET"] = sel["name"]
        payload["__EVENTARGUMENT"] = ""

        action = urljoin(r.url, form.get("action") or r.url)
        posted = self.session.post(action, data=payload, timeout=25, allow_redirects=True, headers={"Referer": r.url})
        posted.raise_for_status()
        if self._is_botstopper(posted):
            raise SkolaOnlineError("BotStopper zablokoval POST pro výběr třídy.")
        return parse_timetable_html(posted.text, class_name)
