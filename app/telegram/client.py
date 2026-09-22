"""
Telegram → Backend API client.

The bot NEVER touches the database directly.
All data comes from the Flask backend via HTTP.
"""

from __future__ import annotations

from typing import Any

import httpx

from app.config import Config

# ★ Shared HTTP client (connection reuse — 10x faster)
_http_client = httpx.Client(
    timeout=15,
    limits=httpx.Limits(
        max_keepalive_connections=10,
        max_connections=20,
        keepalive_expiry=120,
    ),
)


# ★ Shared HTTP client (connection reuse — 10x faster)
import httpx as _httpx
_http_client = _httpx.Client(
    timeout=15,
    limits=_httpx.Limits(
        max_keepalive_connections=10,
        max_connections=20,
        keepalive_expiry=120,
    ),
)




# ============================================================
# HTTP POST with retry (exponential backoff)
# ============================================================
def _post_with_retry(url: str, *, json=None, data=None, files=None,
                     timeout: int = 30, retries: int = 3):
    """POST with retry on network errors (timeout, handshake, connection).

    Retries: 3 (default) with 1s, 2s backoff.
    Does NOT retry: HTTP 4xx (permanent errors).
    """
    import time
    import httpx
    import logging
    log = logging.getLogger(__name__)

    last_err = None
    for attempt in range(retries):
        try:
            return _http_client.post(url, json=json, data=data,
                              files=files, timeout=timeout)
        except Exception as e:
            last_err = e
            err_str = str(e).lower()
            is_network = any(k in err_str for k in (
                "timeout", "handshake", "connection",
                "network", "ssl",
            ))
            if not is_network:
                raise   # permanent error → don't retry

            if attempt < retries - 1:
                wait = 2 ** attempt   # 1s, 2s
                log.warning("retry %d/%d after %ds: %s",
                            attempt + 1, retries, wait, e)
                time.sleep(wait)
                continue
            break   # last attempt → give up

    raise last_err



def _resize_photo(path: str, max_px: int = 800, quality: int = 85) -> str:
    """
    Resize an image to max_px, return new temp file path.
    Returns original path if resize fails or already small.
    """
    try:
        from PIL import Image
        import tempfile
        import os

        size = os.path.getsize(path)
        # Skip if already small (< 200 KB)
        if size < 200 * 1024:
            return path

        img = Image.open(path)
        # Convert RGBA/CMYK → RGB (JPEG needs RGB)
        if img.mode != "RGB":
            img = img.convert("RGB")

        # Thumbnail preserves aspect ratio
        img.thumbnail((max_px, max_px), Image.LANCZOS)

        tmp = tempfile.NamedTemporaryFile(
            suffix=".jpg", delete=False, prefix="tg_resize_",
        )
        img.save(tmp.name, "JPEG", quality=quality, optimize=True)
        tmp.close()
        return tmp.name
    except Exception as e:
        import logging
        logging.warning("resize failed: %s", e)
        return path


class BackendClient:
    def __init__(self, base_url: str | None = None, timeout: float = 15.0):
        self.base_url = (base_url or Config.TELEGRAM_API_BASE).rstrip("/")
        self.timeout = timeout

    def _auth_headers(self) -> dict:
        """★ API Key header (Bot ↔ API security)."""
        headers = {}
        api_key = getattr(Config, "BOT_API_KEY", "") or ""
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        return headers

    def _get(self, path: str, params: dict | None = None) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        try:
            r = httpx.get(url, params=params, timeout=self.timeout,
                          headers=self._auth_headers())
            r.raise_for_status()
            return r.json()
        except httpx.HTTPError as e:
            return {"success": False, "error": {"code": "http_error", "message": str(e)}}
        except Exception as e:
            return {"success": False, "error": {"code": "error", "message": str(e)}}

    def _post(self, path: str, json_body: dict | None = None) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        try:
            r = _http_client.post(url, json=json_body or {}, timeout=self.timeout,
                                  headers=self._auth_headers())
            r.raise_for_status()
            return r.json()
        except httpx.HTTPError as e:
            return {"success": False, "error": {"code": "http_error", "message": str(e)}}
        except Exception as e:
            return {"success": False, "error": {"code": "error", "message": str(e)}}

    # --- Backend endpoints ---

    def health(self) -> dict[str, Any]:
        return self._get("/health")

    def search_machine_codes(self, shop: str, q: str, limit: int = 20) -> dict[str, Any]:
        return self._get("/api/machine-codes/search",
                         params={"shop": shop, "q": q, "limit": limit})

    def unified_search(self, q: str, shop: str | None = None) -> dict[str, Any]:
        params = {"q": q}
        if shop:
            params["shop"] = shop
        return self._get("/api/search", params=params)

    def ask_ai(self, question: str, shop: str | None = None) -> dict[str, Any]:
        body = {"question": question}
        if shop:
            body["shop"] = shop
        return self._post("/api/ai/ask", json_body=body)

    def tasks_today(self, shop: str | None = None) -> dict[str, Any]:
        params = {}
        if shop:
            params["shop"] = shop
        return self._get("/api/tasks/today", params=params)

    def list_errors(self, shop: str, q: str = "", page: int = 1, per: int = 20) -> dict:
        params = {"shop": shop, "page": page, "per": per}
        if q:
            params["q"] = q
        return self._get("/api/errors/list", params=params)

    def get_error(self, shop: str, ident: str) -> dict:
        return self._get("/api/errors/one", params={"shop": shop, "id": ident})


# ================================================================
# Telegram file uploads (for photos)
# ================================================================
def _api_url(method: str) -> str:
    from app.config import Config
    return f"https://api.telegram.org/bot{Config.TELEGRAM_BOT_TOKEN}/{method}"


def send_photo_via_file(chat_id: int, file_path: str, caption: str = "",
                        message_thread_id: int | None = None) -> dict:
    """Upload a local photo to Telegram."""
    import httpx
    try:
        data = {"chat_id": chat_id, "caption": caption[:1000]}
        if message_thread_id:
            data["message_thread_id"] = message_thread_id
        with open(file_path, "rb") as fh:
            r = _http_client.post(
                _api_url("sendPhoto"),
                data=data,
                files={"photo": fh},
                timeout=30,
            )
        return r.json()
    except Exception as e:
        return {"ok": False, "error": str(e)}


def send_photo_by_file_id(chat_id: int, file_id: str, caption: str = "",
                          message_thread_id: int | None = None) -> dict:
    """Send a photo using an existing Telegram file_id (fast)."""
    import httpx
    try:
        payload = {"chat_id": chat_id, "photo": file_id, "caption": caption[:1000]}
        if message_thread_id:
            payload["message_thread_id"] = message_thread_id
        r = _post_with_retry(
            _api_url("sendPhoto"),
            json=payload,
            timeout=20,
        )
        return r.json()
    except Exception as e:
        return {"ok": False, "error": str(e)}


def send_media_group_by_file_ids(chat_id, file_ids, caption="", message_thread_id=None):
    """Send multiple photos (by Telegram file_id) as an album. Supports thread_id."""
    import httpx
    if not file_ids:
        return {"ok": False, "error": "no file_ids"}

    media = []
    for i, fid in enumerate(file_ids[:10]):
        item = {"type": "photo", "media": fid}
        if i == 0:
            item["caption"] = (caption or "")[:1000]
            item["parse_mode"] = "HTML"
        media.append(item)

    payload = {"chat_id": chat_id, "media": media}
    if message_thread_id:
        payload["message_thread_id"] = message_thread_id

    try:
        r = _http_client.post(_api_url("sendMediaGroup"), json=payload, timeout=60)
        return r.json()
    except Exception as e:
        return {"ok": False, "error": str(e)}

def send_media_group_by_paths(chat_id, paths, caption="", message_thread_id=None):
    """Send multiple local photos as an album. Supports thread_id."""
    import httpx
    import json as _json
    if not paths:
        return {"ok": False, "error": "no paths"}

    media = []
    files = {}
    for i, path in enumerate(paths[:10]):
        attach = "file%d" % i
        item = {"type": "photo", "media": "attach://" + attach}
        if i == 0:
            item["caption"] = (caption or "")[:1000]
            item["parse_mode"] = "HTML"
        media.append(item)
        try:
            files[attach] = open(path, "rb")
        except Exception as e:
            return {"ok": False, "error": "open failed: " + str(e)}

    data = {"chat_id": chat_id, "media": _json.dumps(media)}
    if message_thread_id:
        data["message_thread_id"] = message_thread_id

    try:
        r = _post_with_retry(_api_url("sendMediaGroup"),
                       data=data, files=files, timeout=120)
        return r.json()
    except Exception as e:
        return {"ok": False, "error": str(e)}
    finally:
        for fh in files.values():
            try:
                fh.close()
            except Exception:
                pass

def _cleanup_temp(path: str) -> None:
    """Remove temp file if it looks like our temp."""
    try:
        import os
        if "tg_resize_" in path and os.path.exists(path):
            os.remove(path)
    except Exception:
        pass


def upload_photo_get_file_id(chat_id: int, file_path: str,
                              caption: str = "") -> dict:
    """
    Upload a photo with resize, and return its Telegram file_id.

    Returns:
        {"ok": bool, "file_id": str | None, "error": str | None}
    """
    import httpx

    # B: resize before upload
    resized = _resize_photo(file_path)

    try:
        with open(resized, "rb") as fh:
            r = _http_client.post(
                _api_url("sendPhoto"),
                data={"chat_id": chat_id, "caption": caption[:1000]},
                files={"photo": fh},
                timeout=60,
            )
        data = r.json()
        if not data.get("ok"):
            return {
                "ok": False,
                "file_id": None,
                "error": data.get("description") or str(data),
            }
        # Telegram sends array of sizes; take the largest (last)
        photos = (data.get("result") or {}).get("photo") or []
        message_id = (data.get("result") or {}).get("message_id")
        if photos:
            file_id = photos[-1].get("file_id")
            return {"ok": True, "file_id": file_id,
                    "message_id": message_id, "error": None}
        return {"ok": True, "file_id": None,
                "message_id": message_id, "error": "no photo in response"}
    except Exception as e:
        return {"ok": False, "file_id": None, "error": str(e)}
    finally:
        if resized != file_path:
            _cleanup_temp(resized)


def delete_message(chat_id: int, message_id: int) -> dict:
    """Delete a message from a chat."""
    import httpx
    try:
        r = _http_client.post(
            _api_url("deleteMessage"),
            json={"chat_id": chat_id, "message_id": message_id},
            timeout=15,
        )
        return r.json()
    except Exception as e:
        return {"ok": False, "error": str(e)}


def send_media_group_with_cache(
    chat_id,
    photos,
    caption="",
    save_callback=None,
    admin_chat_id=None,
    message_thread_id=None,
):
    """A+B optimized album send. Supports message_thread_id."""
    import httpx
    import json as _json
    import logging
    log = logging.getLogger(__name__)

    if not photos:
        return {"ok": False, "error": "no photos"}

    cached = [getattr(p, "telegram_file_id", None) for p in photos]

    # Case 1: all cached → instant JSON album
    if all(cached):
        media = []
        for i, fid in enumerate(cached[:10]):
            item = {"type": "photo", "media": fid}
            if i == 0:
                item["caption"] = (caption or "")[:1000]
                item["parse_mode"] = "HTML"
            media.append(item)

        payload = {"chat_id": chat_id, "media": media}
        if message_thread_id:
            payload["message_thread_id"] = message_thread_id

        try:
            r = _post_with_retry(_api_url("sendMediaGroup"), json=payload, timeout=30)
            return r.json()
        except Exception as e:
            log.warning("album (cached) failed: %s", e)
            return {"ok": False, "error": str(e)}

    # Case 2: multipart
    files = {}
    media = []
    opened = []

    try:
        for i, p in enumerate(photos[:10]):
            fp = getattr(p, "file_path", None)
            if not fp:
                continue
            if getattr(p, "telegram_file_id", None):
                # 1. Cached Telegram file_id → direct
                item = {"type": "photo", "media": p.telegram_file_id}
            elif isinstance(fp, str) and fp.startswith(("http://", "https://")):
                # 2. ★ Public URL → Telegram can fetch directly
                item = {"type": "photo", "media": fp}
            else:
                # 3. Local file → resize + multipart upload
                resized = _resize_photo(fp)
                try:
                    fh = open(resized, "rb")
                    opened.append((fh, resized if resized != fp else None))
                    attach = "file%d" % i
                    files[attach] = fh
                    item = {"type": "photo", "media": "attach://" + attach}
                except Exception as e:
                    log.warning("open failed: %s", e)
                    continue
            if i == 0:
                item["caption"] = (caption or "")[:1000]
                item["parse_mode"] = "HTML"
            media.append(item)

        if not media:
            return {"ok": False, "error": "no media"}

        data = {"chat_id": chat_id, "media": _json.dumps(media)}
        if message_thread_id:
            data["message_thread_id"] = message_thread_id

        r = _http_client.post(_api_url("sendMediaGroup"),
                       data=data, files=files, timeout=120)
        data_r = r.json()

        if data_r.get("ok") and save_callback:
            results = data_r.get("result") or []
            idx = 0
            for p in photos[:10]:
                if not getattr(p, "file_path", None) and not getattr(p, "telegram_file_id", None):
                    continue
                if getattr(p, "telegram_file_id", None):
                    idx += 1
                    continue
                if idx < len(results):
                    arr = results[idx].get("photo") or []
                    if arr:
                        try:
                            save_callback(p.id, arr[-1].get("file_id"))
                        except Exception as e:
                            log.warning("save file_id failed: %s", e)
                idx += 1
        return data_r
    except Exception as e:
        log.warning("multipart album failed: %s", e)
        return {"ok": False, "error": str(e)}
    finally:
        for fh, tmp in opened:
            try:
                fh.close()
            except Exception:
                pass
            if tmp:
                _cleanup_temp(tmp)