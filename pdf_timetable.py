from __future__ import annotations
import re
from pathlib import Path
import pdfplumber

DAYS = ["Po", "Út", "St", "Čt", "Pá"]
ROOM_RE = re.compile(r"^(?:U\d+|Slávie|Slavie)$", re.I)


def _join(words):
    return " ".join(w["text"] for w in sorted(words, key=lambda x: x["x0"])).strip()


def parse_timetable_pdf(path: str | Path):
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(path)
    with pdfplumber.open(path) as pdf:
        page = pdf.pages[0]
        words = page.extract_words(x_tolerance=1.5, y_tolerance=2)

    # Třída
    full_text = " ".join(w["text"] for w in words)
    m = re.search(r"Třída:\s*([A-Za-z0-9._-]+)", full_text)
    class_name = m.group(1) if m else "BB1A"

    # Sloupce hodin podle čísel 0..13 v horním řádku.
    heads = []
    for w in words:
        if w["top"] < 90 and w["text"].isdigit() and 0 <= int(w["text"]) <= 13:
            heads.append((int(w["text"]), (w["x0"] + w["x1"]) / 2))
    heads = sorted(dict(heads).items())
    centers = [x for _, x in heads]
    periods = [n for n, _ in heads]
    if len(centers) < 9:
        raise ValueError("V PDF se nepodařilo najít hlavičku hodin 0-13.")
    step = sum(b-a for a,b in zip(centers, centers[1:])) / (len(centers)-1)
    x_bounds = [centers[0]-step/2] + [(a+b)/2 for a,b in zip(centers, centers[1:])] + [centers[-1]+step/2]

    # Řádky dnů podle popisků Po-Pá vlevo.
    day_marks = []
    for w in words:
        if w["text"] in DAYS and w["x0"] < 75 and 90 < w["top"] < 650:
            day_marks.append((w["text"], w["top"]))
    day_marks.sort(key=lambda z: z[1])
    if len(day_marks) < 5:
        raise ValueError("V PDF se nepodařilo najít řádky Po-Pá.")
    marker_ys = [y for _, y in day_marks]
    mids = [(a+b)/2 for a,b in zip(marker_ys, marker_ys[1:])]
    day_tops = [94] + mids
    day_bottoms = mids + [marker_ys[-1] + 70]

    result_days = []
    for di, (day, marker_y) in enumerate(day_marks[:5]):
        y0, y1 = day_tops[di], day_bottoms[di]
        date_words = [w for w in words if w["x0"] < 75 and y0 <= w["top"] < y1 and re.match(r"^\d{1,2}\.\d{1,2}\.$", w["text"])]
        date_label = date_words[0]["text"] if date_words else ""
        lessons = []
        for pi, period in enumerate(periods):
            x0, x1 = x_bounds[pi], x_bounds[pi+1]
            cell = [w for w in words if x0 <= (w["x0"]+w["x1"])/2 < x1 and y0 <= w["top"] < y1]
            if not cell:
                continue
            # seskupení do řádků podle top
            lines = []
            for w in sorted(cell, key=lambda z:(z["top"],z["x0"])):
                target = None
                for line in lines:
                    if abs(line[0]["top"] - w["top"]) < 2.2:
                        target = line; break
                if target is not None:
                    target.append(w)
                else:
                    lines.append([w])
            line_texts = [(_join(line), line[0]["top"]) for line in lines]
            groups = []
            for idx, (txt, top) in enumerate(line_texts):
                if txt == class_name and idx >= 1:
                    subject = line_texts[idx-1][0]
                    teacher = line_texts[idx+1][0] if idx+1 < len(line_texts) else ""
                    room = line_texts[idx+2][0] if idx+2 < len(line_texts) and ROOM_RE.match(line_texts[idx+2][0]) else ""
                    # ochrana před tím, že další blok začne hned dalším předmětem
                    if teacher == class_name or ROOM_RE.match(teacher):
                        teacher = ""
                    groups.append({"name":"", "subject":subject, "teacher":teacher, "room":room, "_top":top})
            # odstranění duplicit vzniklých překryvem textu
            clean=[]
            for g in groups:
                key=(g['subject'],g['teacher'],g['room'],round(g['_top'],1))
                if not any((x['subject'],x['teacher'],x['room'],round(x['_top'],1))==key for x in clean): clean.append(g)
            for g in clean: g.pop('_top',None)
            if clean:
                if len(clean)==1:
                    l={"period":period, **clean[0]}
                    l.pop("name",None)
                else:
                    l={"period":period,"groups":clean}
                lessons.append(l)
        result_days.append({"short":day,"date":date_label,"lessons":lessons})
    return {"class_name":class_name,"source":"pdf-test","days":result_days,"holiday":False}
