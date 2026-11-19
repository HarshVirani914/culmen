import shutil
from pathlib import Path


def _size(p: Path) -> int:
    return sum(f.stat().st_size for f in p.rglob("*") if f.is_file()) if p.exists() else 0


def enforce_cap(root: Path, ids: list[str], cap_bytes: int, keep: set[str]) -> list[str]:
    """Delete directories `root/<id>` (ids ordered oldest to newest) until their total size is under the cap.
    Ids in `keep` are never deleted. Returns the deleted ids."""
    sizes = {i: _size(root / i) for i in ids}
    total = sum(sizes.values())
    deleted: list[str] = []
    for i in ids:
        if total <= cap_bytes:
            break
        if i in keep or not (root / i).exists():
            continue
        shutil.rmtree(root / i, ignore_errors=True)
        total -= sizes[i]
        deleted.append(i)
    return deleted
