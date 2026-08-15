from __future__ import annotations
import getpass
import os
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv, set_key

from skola_online import SkolaOnlineClient

BASE = Path(__file__).resolve().parent
CFG = BASE / "sync_config.env"

def ask(label, secret=False):
    return (getpass.getpass(label) if secret else input(label)).strip()

def ensure_config():
    if CFG.exists():
        load_dotenv(CFG, override=True)

    keys = ["BANNER_RENDER_URL","BANNER_SYNC_TOKEN","SKOLAONLINE_USER","SKOLAONLINE_PASSWORD"]
    if all(os.environ.get(k) for k in keys):
        return

    print("\\n=== PRVNI NASTAVENI ===")
    url = ask("Adresa Render banneru: ").rstrip("/")
    token = ask("Synchronizacni klic z /admin: ")
    user = ask("Uzivatelske jmeno Skola Online: ")
    password = ask("Heslo Skola Online: ", secret=True)

    CFG.touch(exist_ok=True)
    set_key(str(CFG), "BANNER_RENDER_URL", url)
    set_key(str(CFG), "BANNER_SYNC_TOKEN", token)
    set_key(str(CFG), "SKOLAONLINE_USER", user)
    set_key(str(CFG), "SKOLAONLINE_PASSWORD", password)
    load_dotenv(CFG, override=True)

def main():
    ensure_config()
    base_url = os.environ["BANNER_RENDER_URL"].rstrip("/")
    token = os.environ["BANNER_SYNC_TOKEN"]
    client = SkolaOnlineClient(
        os.environ["SKOLAONLINE_USER"],
        os.environ["SKOLAONLINE_PASSWORD"]
    )

    print("\\n[1/3] Prihlasuji se do Skoly Online...")
    classes = client.get_classes()

    print("[2/3] Nacitam aktualni tyden...")
    timetables = {}
    for i, item in enumerate(classes, 1):
        name = item.get("name") or item.get("value")
        if not name:
            continue
        print(f"  {i}/{len(classes)}  {name}")
        try:
            timetables[name] = client.get_timetable(name)
        except Exception as exc:
            print(f"    CHYBA: {exc}")

    if not timetables:
        raise RuntimeError("Nepodarilo se nacist zadny rozvrh.")

    print(f"[3/3] Odesilam {len(timetables)} trid na Render...")
    r = requests.post(
        base_url + "/api/sync/timetables",
        headers={"X-Banner-Sync-Token": token},
        json={"timetables": timetables},
        timeout=120
    )
    result = r.json()
    if not r.ok or not result.get("ok"):
        raise RuntimeError(result.get("error") or f"HTTP {r.status_code}")

    print("\\nHOTOVO.")
    print(f"Nahrano trid: {result.get('classes')}")

if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"\\nCHYBA: {exc}")
        sys.exit(1)
