from __future__ import annotations

import json
import os
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import instaloader


class InstagramFeed:
    """Lokální cache posledních příspěvků veřejného Instagram profilu.

    Fotky se stáhnou na disk a GUI pak používá jen lokální soubory, takže
    návštěvník banneru nemůže nic rozkliknout ani přejít na Instagram.
    """

    def __init__(self, base_dir: Path, profile_name: str = "sssaskv", limit: int = 40, refresh_seconds: int = 3600):
        self.base_dir = Path(base_dir)
        self.profile_name = profile_name.lstrip("@").strip()
        self.limit = int(limit)
        self.refresh_seconds = int(refresh_seconds)
        self.image_dir = self.base_dir / "static" / "instagram_posts"
        self.cache_file = self.base_dir / "instagram_cache.json"
        self.image_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._refreshing = False
        self._last_error = ""

    def _read_cache(self) -> dict[str, Any]:
        try:
            data = json.loads(self.cache_file.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                return {}
            data.setdefault("items", [])
            return data
        except Exception:
            return {"items": []}

    def _write_cache(self, data: dict[str, Any]) -> None:
        tmp = self.cache_file.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self.cache_file)

    def _is_stale(self, data: dict[str, Any]) -> bool:
        ts = float(data.get("updated_ts") or 0)
        return (time.time() - ts) > self.refresh_seconds

    def _start_refresh(self) -> None:
        with self._lock:
            if self._refreshing:
                return
            self._refreshing = True
        threading.Thread(target=self._refresh_worker, name="instagram-refresh", daemon=True).start()

    def get_state(self, force_refresh: bool = False) -> dict[str, Any]:
        data = self._read_cache()
        if force_refresh or self._is_stale(data) or not data.get("items"):
            self._start_refresh()
        return {
            "items": data.get("items", [])[: self.limit],
            "updated_at": data.get("updated_at"),
            "refreshing": self._refreshing,
            "error": self._last_error,
            "profile": self.profile_name,
        }

    def _login_if_configured(self, loader: instaloader.Instaloader) -> None:
        # Volitelné vlastní proměnné; pokud nejsou, použijeme přihlašovací údaje,
        # které už aplikace používá pro Školu Online (uživatel uvedl, že jsou stejné).
        username = (os.environ.get("INSTAGRAM_USER") or os.environ.get("SKOLAONLINE_USER") or "").strip()
        password = (os.environ.get("INSTAGRAM_PASSWORD") or os.environ.get("SKOLAONLINE_PASSWORD") or "").strip()
        if not username or not password:
            return
        try:
            loader.login(username, password)
        except Exception:
            # Veřejný profil lze často načíst i bez loginu. Pokud Instagram login
            # odmítne/challenge-ne, pokračujeme anonymně místo otevření prohlížeče.
            pass

    def _download_image(self, loader: instaloader.Instaloader, url: str, destination: Path) -> None:
        response = loader.context.get_raw(url)
        destination.write_bytes(response.read())

    def _refresh_worker(self) -> None:
        try:
            loader = instaloader.Instaloader(
                download_pictures=False,
                download_videos=False,
                download_video_thumbnails=False,
                download_geotags=False,
                download_comments=False,
                save_metadata=False,
                compress_json=False,
                quiet=True,
            )
            self._login_if_configured(loader)
            profile = instaloader.Profile.from_username(loader.context, self.profile_name)

            items: list[dict[str, Any]] = []
            keep_files: set[str] = set()
            for post in profile.get_posts():
                if len(items) >= self.limit:
                    break

                # U carouselu používáme titulní obrázek; u videa jeho cover.
                url = post.url
                shortcode = post.shortcode
                filename = f"{len(items):02d}_{shortcode}.jpg"
                destination = self.image_dir / filename
                try:
                    if not destination.exists() or destination.stat().st_size < 1000:
                        self._download_image(loader, url, destination)
                except Exception:
                    continue

                keep_files.add(filename)
                caption = (post.caption or "").strip().replace("\n", " ")
                items.append({
                    "image": f"instagram_posts/{filename}",
                    "shortcode": shortcode,
                    "date": post.date_local.strftime("%d.%m.%Y"),
                    "caption": caption[:220],
                })

            if not items:
                raise RuntimeError("Instagram nevrátil žádné příspěvky.")

            # Staré obrázky z cache odstraníme, aby se složka nezvětšovala donekonečna.
            for path in self.image_dir.glob("*.jpg"):
                if path.name not in keep_files:
                    try:
                        path.unlink()
                    except OSError:
                        pass

            now = datetime.now()
            self._write_cache({
                "profile": self.profile_name,
                "updated_ts": time.time(),
                "updated_at": now.strftime("%d.%m.%Y %H:%M"),
                "items": items,
            })
            self._last_error = ""
        except Exception as exc:
            self._last_error = str(exc)
        finally:
            with self._lock:
                self._refreshing = False
