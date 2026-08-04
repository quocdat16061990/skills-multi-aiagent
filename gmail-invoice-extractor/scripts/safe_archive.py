from __future__ import annotations

import io, zipfile
from pathlib import Path, PurePosixPath

ALLOWED = {".pdf", ".xml", ".jpg", ".jpeg", ".png"}

def extract_zip(data: bytes, destination: Path, max_files: int = 100, max_member_bytes: int = 25_000_000, max_total_bytes: int = 100_000_000) -> list[Path]:
    out, total = [], 0
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        infos = [i for i in z.infolist() if not i.is_dir()]
        if len(infos) > max_files: raise ValueError("ZIP file-count limit exceeded")
        for i in infos:
            p = PurePosixPath(i.filename.replace("\\", "/"))
            if p.is_absolute() or ".." in p.parts: raise ValueError("unsafe ZIP member path")
            if i.file_size > max_member_bytes: raise ValueError("ZIP member size limit exceeded")
            total += i.file_size
            if total > max_total_bytes: raise ValueError("ZIP total size limit exceeded")
            if p.suffix.lower() not in ALLOWED: continue
            target = destination.joinpath(*p.parts).resolve()
            root = destination.resolve()
            if root not in target.parents: raise ValueError("unsafe ZIP extraction target")
            target.parent.mkdir(parents=True, exist_ok=True)
            written = 0
            with z.open(i) as src, target.open("wb") as dst:
                while True:
                    chunk = src.read(1024 * 1024)
                    if not chunk: break
                    written += len(chunk)
                    if written > max_member_bytes or written > i.file_size + 1: raise ValueError("ZIP expanded beyond declared size")
                    dst.write(chunk)
            out.append(target)
    return out
