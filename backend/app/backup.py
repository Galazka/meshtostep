"""DB backup — pg_dump (Postgres) or file copy (SQLite) into DATA_DIR/backups. Keeps last 7."""
import gzip
import os
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

from .config import settings


def backup_dir() -> Path:
    d = Path(settings.DATA_DIR) / "backups"
    d.mkdir(parents=True, exist_ok=True)
    return d


def backup_db() -> str | None:
    """Run one backup. Returns backup filename or None on failure."""
    url = settings.DATABASE_URL or ""
    stamp = datetime.utcnow().strftime("%Y%m%d-%H%M")
    try:
        if url.startswith("sqlite"):
            src = url.split("///", 1)[-1]
            if not os.path.exists(src):
                return None
            dst = backup_dir() / f"sqlite-{stamp}.db"
            shutil.copy2(src, dst)
        else:
            dst = backup_dir() / f"pg-{stamp}.sql.gz"
            env = dict(os.environ)
            p = subprocess.run(
                ["pg_dump", url, "--no-owner", "--no-acl"],
                capture_output=True, timeout=300, env=env,
            )
            if p.returncode != 0 or not p.stdout:
                print(f"[backup] pg_dump failed: {p.stderr.decode()[:200]}")
                return None
            with gzip.open(dst, "wb") as f:
                f.write(p.stdout)
        print(f"[backup] wrote {dst.name} ({dst.stat().st_size // 1024} KB)")
        # prune: keep newest 7
        files = sorted(backup_dir().glob("*.gz")) + sorted(backup_dir().glob("*.db"))
        files = sorted(files, key=lambda x: x.name)
        for old in files[:-7]:
            old.unlink(missing_ok=True)
        return dst.name
    except Exception as e:
        print(f"[backup] error: {e}")
        return None


def list_backups() -> list:
    out = []
    for f in sorted(backup_dir().glob("*"), key=lambda x: x.name, reverse=True):
        if f.is_file():
            out.append({"name": f.name, "size_kb": f.stat().st_size // 1024})
    return out
