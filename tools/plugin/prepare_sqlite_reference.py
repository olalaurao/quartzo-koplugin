"""Read only allowlisted hash-pinned files from an official, downloaded archive."""
import argparse
import hashlib
import json
from pathlib import Path
import tarfile

LOCK = Path(__file__).with_name("SQLITE_REFERENCE.lock.json")


def verify(directory):
    lock = json.loads(LOCK.read_text())
    for name, expected in lock["files"].items():
        path = directory / name
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 2 * 1024 * 1024:
            raise ValueError("Unsupported SQLite reference")
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError("SQLite reference hash mismatch")
    return lock


def prepare(archive, output):
    lock = json.loads(LOCK.read_text())
    with archive.open("rb") as handle:
        if hashlib.file_digest(handle, "sha256").hexdigest() != lock["archive_sha256"]:
            raise ValueError("Official KOReader archive hash mismatch")
    output.mkdir(exist_ok=False)
    with tarfile.open(archive, "r:xz") as tar:
        for name in lock["files"]:
            member = tar.getmember("lib/koreader/" + name)
            if not member.isfile() or member.size > 2 * 1024 * 1024:
                raise ValueError("Unsupported SQLite archive entry")
            path = output / name
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("xb") as handle:
                handle.write(tar.extractfile(member).read(2 * 1024 * 1024 + 1))
            if name == "luajit":
                path.chmod(0o700)
    verify(output)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    prepare(args.archive, args.output)
    print("PASS: exact test-only KOReader SQLite wrapper/library prepared")
