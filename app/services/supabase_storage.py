"""
Supabase Storage — Direct HTTP upload (no supabase-py library).
Uses httpx which is already a dependency.
"""
from __future__ import annotations

import os
import logging
from pathlib import Path
from typing import Optional

import httpx

log = logging.getLogger(__name__)


def _get_config():
    """Read Supabase config from environment."""
    url = (os.getenv("SUPABASE_URL") or "").strip().rstrip("/")
    key = (os.getenv("SUPABASE_SERVICE_KEY") or "").strip()
    bucket = (os.getenv("SUPABASE_STORAGE_BUCKET") or "knowledge-photos").strip()
    return url, key, bucket


def is_configured() -> bool:
    url, key, bucket = _get_config()
    return bool(url and key and bucket)


def upload_file(
    local_path: str | Path,
    remote_path: str,
    content_type: str = "application/octet-stream",
) -> Optional[str]:
    """
    Upload a local file to Supabase Storage.

    Returns public URL on success, None on failure.
    """
    url, key, bucket = _get_config()
    if not (url and key):
        log.warning("Supabase Storage not configured — skip upload")
        return None

    p = Path(local_path)
    if not p.is_file():
        log.warning("Local file not found: %s", p)
        return None

    remote_path = remote_path.lstrip("/")
    upload_url = f"{url}/storage/v1/object/{bucket}/{remote_path}"

    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": content_type,
        "x-upsert": "true",
        "Cache-Control": "3600",
    }

    try:
        with open(p, "rb") as fh:
            data = fh.read()

        with httpx.Client(timeout=30) as client:
            r = client.post(upload_url, headers=headers, content=data)

        if r.status_code in (200, 201):
            public_url = f"{url}/storage/v1/object/public/{bucket}/{remote_path}"
            log.info("Uploaded to Supabase: %s", public_url)
            return public_url

        log.error(
            "Supabase upload failed [%s]: %s",
            r.status_code, r.text[:300],
        )
        return None
    except Exception as e:
        log.exception("Supabase upload exception: %s", e)
        return None


def delete_file(remote_path: str) -> bool:
    """Delete a file from Supabase Storage."""
    url, key, bucket = _get_config()
    if not (url and key):
        return False

    remote_path = remote_path.lstrip("/")
    delete_url = f"{url}/storage/v1/object/{bucket}/{remote_path}"

    try:
        with httpx.Client(timeout=15) as client:
            r = client.delete(
                delete_url,
                headers={"Authorization": f"Bearer {key}"},
            )
        return r.status_code in (200, 204)
    except Exception as e:
        log.warning("Supabase delete failed: %s", e)
        return False
