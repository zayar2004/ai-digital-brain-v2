"""
Backup + Restore service.

- Creates a zip of: DB file + uploads directory
- Lists available backups
- Restores DB from a backup (with safety check)
"""

from __future__ import annotations

import json
import os
import shutil
import zipfile
from datetime import datetime
from pathlib import Path

from app.config import BASE_DIR, INSTANCE_DIR, UPLOAD_ROOT

BACKUP_DIR = BASE_DIR / "backups"
BACKUP_DIR.mkdir(parents=True, exist_ok=True)


def _db_path() -> Path | None:
    from app.config import Config
    uri = Config.SQLALCHEMY_DATABASE_URI
    if uri.startswith("sqlite:///"):
        p = uri.replace("sqlite:///", "", 1)
        # Handle absolute path
        if p.startswith("/"):
            p = p[1:]
        return Path(p)
    return None


def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def create_backup(*, label: str | None = None) -> Path:
    """Create a backup zip. Returns path."""
    ts = _timestamp()
    tag = f"_{label}" if label else ""
    out_path = BACKUP_DIR / f"backup_{ts}{tag}.zip"

    meta = {
        "created_at": datetime.now().isoformat(),
        "label": label or "",
        "db_path": str(_db_path()) if _db_path() else None,
        "uploads_root": str(UPLOAD_ROOT),
    }

    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as zf:
        # DB
        db_p = _db_path()
        if db_p and db_p.is_file():
            zf.write(db_p, arcname=f"db/{db_p.name}")

        # Uploads
        for root, _dirs, files in os.walk(UPLOAD_ROOT):
            for f in files:
                full = Path(root) / f
                rel = full.relative_to(UPLOAD_ROOT.parent)
                zf.write(full, arcname=str(rel))

        # Meta
        zf.writestr("meta.json", json.dumps(meta, indent=2, ensure_ascii=False))

    return out_path


def list_backups() -> list[dict]:
    """Return list of {name, path, size, created}."""
    out = []
    for p in sorted(BACKUP_DIR.glob("backup_*.zip"), reverse=True):
        stat = p.stat()
        out.append({
            "name": p.name,
            "size_bytes": stat.st_size,
            "created_at": datetime.fromtimestamp(stat.st_mtime),
            "path": str(p),
        })
    return out


def restore_backup(backup_name: str, *, confirm: bool = False) -> dict:
    """
    Restore DB from a backup.

    Before restoring, we first create a safety backup of the current DB.
    """
    if not confirm:
        return {"ok": False, "error": "confirm required"}

    src = BACKUP_DIR / backup_name
    if not src.is_file() or not src.name.startswith("backup_"):
        return {"ok": False, "error": "invalid backup name"}

    # Safety backup
    safety = create_backup(label="before_restore")

    # Close DB connections
    from app.extensions import db
    try:
        db.session.remove()
        db.engine.dispose()
    except Exception:
        pass

    # Extract db file
    db_p = _db_path()
    if not db_p:
        return {"ok": False, "error": "not a SQLite database"}

    try:
        with zipfile.ZipFile(src, "r") as zf:
            db_members = [n for n in zf.namelist() if n.startswith("db/")]
            if not db_members:
                return {"ok": False, "error": "no DB in backup"}
            db_member = db_members[0]
            # Backup current DB
            if db_p.is_file():
                shutil.copy2(db_p, db_p.with_suffix(db_p.suffix + ".pre_restore"))
            # Write restored DB
            with zf.open(db_member) as fh:
                with open(db_p, "wb") as out:
                    shutil.copyfileobj(fh, out)
    except Exception as e:
        return {"ok": False, "error": str(e)}

    return {
        "ok": True,
        "restored": src.name,
        "safety_backup": safety.name,
    }


def delete_backup(backup_name: str) -> bool:
    p = BACKUP_DIR / backup_name
    if p.is_file() and p.name.startswith("backup_"):
        p.unlink()
        return True
    return False
