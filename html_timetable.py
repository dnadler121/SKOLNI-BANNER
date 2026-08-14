from __future__ import annotations

import html as html_module
import re
from collections import defaultdict
from bs4 import BeautifulSoup

DAYS = ("Po", "Út", "St", "Čt", "Pá")

class HtmlTimetableError(RuntimeError):
    pass


def _clean(value: str | None) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def _tooltip_fields(raw: str | None) -> dict[str, str]:
    if not raw:
        return {}
    text = html_module.unescape(raw)
    # onMouseOverTooltip('SUBJECT','Učitel:~...~Třída:~...')
    text = text.replace("\\'", "'")
    fields: dict[str, str] = {}
    for key in ("Učitel", "Třída", "Žáci", "Učebna", "Cyklus", "Den (vyuč. hodina)", "Čas výuky", "Informace o akci"):
        m = re.search(rf"{re.escape(key)}:~(.*?)(?=~(?:Učitel|Třída|Žáci|Učebna|Cyklus|Den \(vyuč\. hodina\)|Čas výuky|Informace o akci):~|$)", text, re.S)
        if m:
            fields[key] = _clean(m.group(1))
    return fields


def _day_period(fields: dict[str, str]):
    value = fields.get("Den (vyuč. hodina)", "")
    m = re.search(r"\b(Po|Út|St|Čt|Pá)\s+(\d{1,2}\.\d{1,2}\.)\s*\((\d{1,2})\)", value)
    if not m:
        return None
    return m.group(1), m.group(2), int(m.group(3))


def _selected_class(soup: BeautifulSoup) -> str:
    sel = soup.select_one("select#DDLTrida, select[name='DDLTrida']")
    if sel:
        opt = sel.find("option", selected=True)
        if opt:
            return _clean(opt.get_text(" ", strip=True))
    return ""


def parse_timetable_html(html_text: str, expected_class: str | None = None) -> dict:
    soup = BeautifulSoup(html_text, "html.parser")
    table = soup.select_one("table#CCADynamicCalendarTable")
    if table is None:
        raise HtmlTimetableError("HTML neobsahuje tabulku CCADynamicCalendarTable.")

    class_name = _selected_class(soup) or (expected_class or "")
    if expected_class and class_name and class_name.casefold() != expected_class.casefold():
        raise HtmlTimetableError(f"Škola Online vrátila třídu {class_name}, očekávána byla {expected_class}.")

    day_dates: dict[str, str] = {}
    for th in table.find_all("th"):
        texts = [_clean(x) for x in th.stripped_strings]
        if len(texts) >= 2 and texts[0] in DAYS and re.fullmatch(r"\d{1,2}\.\d{1,2}\.", texts[1]):
            day_dates[texts[0]] = texts[1]

    buckets = defaultdict(list)

    # Běžné rozvrhové hodiny. Tooltip obsahuje den i číslo hodiny, takže
    # fungují i dělené hodiny bez odhadování pozice buňky v tabulce.
    for td in table.select("td.DctInnerTableType10DataTD"):
        fields = _tooltip_fields(td.get("onmouseover"))
        dp = _day_period(fields)
        if not dp:
            continue
        day, date_text, period = dp
        subject_el = td.select_one(".KuvBunkaRozvrhNadpis")
        subject = _clean(subject_el.get_text(" ", strip=True) if subject_el else "")
        visible = list(td.stripped_strings)
        teacher = fields.get("Učitel", "")
        room = fields.get("Učebna", "")
        if not teacher and len(visible) >= 2:
            teacher = _clean(visible[-2])
        if not room and visible:
            room = _clean(visible[-1])
        buckets[(day, period)].append({
            "subject": subject,
            "teacher": teacher,
            "room": room,
        })
        day_dates.setdefault(day, date_text)

    # Školní akce mají jinou CSS třídu, ale stejný tooltipový údaj o dni/hodině.
    for td in table.select("td.KuvSkolniAkceHodina"):
        fields = _tooltip_fields(td.get("onmouseover"))
        dp = _day_period(fields)
        if not dp:
            continue
        day, date_text, period = dp
        first_text = _clean(next(iter(td.stripped_strings), "Školní akce"))
        buckets[(day, period)].append({
            "subject": first_text or "Školní akce",
            "teacher": fields.get("Učitel", ""),
            "room": fields.get("Učebna", ""),
            "event": True,
        })
        day_dates.setdefault(day, date_text)

    table_text = _clean(table.get_text(" ", strip=True))
    holiday = bool(re.search(r"\bprázdniny\b", table_text, re.I))

    days = []
    for short in DAYS:
        lessons = []
        for period in range(0, 14):
            entries = buckets.get((short, period), [])
            if not entries:
                continue
            # deduplikace stejných kartiček
            unique = []
            seen = set()
            for e in entries:
                key = (e.get("subject", ""), e.get("teacher", ""), e.get("room", ""), bool(e.get("event")))
                if key not in seen:
                    seen.add(key)
                    unique.append(e)
            if len(unique) == 1:
                lessons.append({"period": period, **unique[0]})
            else:
                lessons.append({
                    "period": period,
                    "subject": "", "teacher": "", "room": "",
                    "groups": [{"name": f"{i+1}. skupina", **e} for i, e in enumerate(unique)]
                })
        days.append({"short": short, "date": day_dates.get(short, ""), "lessons": lessons})

    return {
        "class_name": class_name or (expected_class or ""),
        "days": days,
        "holiday": holiday,
        "source": "html",
    }
