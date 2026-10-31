"""Extract a Debian package (.deb) on any OS without ar/7z/dpkg.

A .deb is an `ar` archive holding `debian-binary`, `control.tar.*` and
`data.tar.*`. This script parses the ar container itself (no external tools)
and unpacks `data.tar` into the requested directory, so the same verification
can run on a Windows or macOS build host:

    python scripts/extract_deb.py MRRS-Setup-1.18.31-arm64.deb out/

Why: ARM64 packages are built on CI, but their frozen backend can be verified
anywhere -- extract `data.tar` and point `scripts/verify_frozen_modules.py`
at the bundled `backend/` directory. That is how the v1.18.29 `difflib`
regression is proven absent from the published artifact instead of trusting
the build log.

Supported compression: .xz (default for dpkg) and .gz. `.zst` needs an
external zstd and is rejected with a clear message.
"""

from __future__ import annotations

import gzip
import io
import lzma
import sys
import tarfile
from pathlib import Path
from typing import Iterator

_AR_MAGIC = b"!<arch>\n"
_HEADER_SIZE = 60


def iter_ar_members(fp) -> Iterator[tuple[str, bytes]]:
    """Yield (name, payload) for every member of an ar archive."""
    if fp.read(len(_AR_MAGIC)) != _AR_MAGIC:
        raise SystemExit("not an ar archive (missing !<arch> magic)")
    while True:
        header = fp.read(_HEADER_SIZE)
        if len(header) < _HEADER_SIZE:
            return
        name = header[0:16].decode("utf-8", "replace").strip().rstrip("/")
        try:
            size = int(header[48:58].decode("ascii").strip())
        except ValueError:
            raise SystemExit(f"corrupted ar header for member {name!r}")
        payload = fp.read(size)
        if len(payload) != size:
            raise SystemExit(f"truncated ar member {name!r}")
        if size % 2:  # members are 2-byte aligned
            fp.read(1)
        yield name, payload


def extract_deb(deb: Path, out_dir: Path) -> Path:
    """Extract data.tar.* from *deb* into *out_dir*; return the extraction root."""
    out_dir.mkdir(parents=True, exist_ok=True)
    with deb.open("rb") as fp:
        for name, payload in iter_ar_members(fp):
            if not name.startswith("data.tar"):
                continue
            if name.endswith(".xz"):
                raw = lzma.decompress(payload)
            elif name.endswith(".gz"):
                raw = gzip.decompress(payload)
            elif name.endswith(".zst"):
                raise SystemExit("data.tar.zst is not supported here; extract with zstd first")
            elif name.endswith(".tar"):
                raw = payload
            else:
                raise SystemExit(f"unknown data member compression: {name}")
            print(f"[deb] extracting {name} ({len(payload)} bytes) -> {out_dir}")
            with tarfile.open(fileobj=io.BytesIO(raw)) as tar:
                tar.extractall(out_dir, filter="data")
            return out_dir
    raise SystemExit("no data.tar member found in package")


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print(__doc__)
        return 2
    deb = Path(argv[1])
    if not deb.is_file():
        print(f"[deb] not found: {deb}")
        return 2
    root = extract_deb(deb, Path(argv[2]))
    print(f"[deb] done: {root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
