"""Fetch exact host-only dependency references into a fresh explicit directory."""
import argparse
import base64
import hashlib
import io
import json
import pathlib
import tarfile
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent
LIMIT = 1048576


def fetch(url):
    request = urllib.request.Request(url, headers={"User-Agent": "quartzo-reading-wire-reference-test"})
    with urllib.request.urlopen(request, timeout=30) as response:
        data = response.read(LIMIT + 1)
    if len(data) > LIMIT:
        raise ValueError("Reference response exceeds bound")
    return data


def verify_reference(directory):
    lock = json.loads((ROOT / "REFERENCE_RUNTIME.lock.json").read_text(encoding="utf-8"))
    for name in ("dkjson", "sha2"):
        entry = lock[name]
        path = directory / entry["file"]
        if path.is_symlink() or not path.is_file() or path.stat().st_size > LIMIT:
            raise ValueError("Invalid reference input")
        data = path.read_bytes()
        if hashlib.sha256(data).hexdigest() != entry["sha256"]:
            raise ValueError("Reference SHA-256 mismatch")
        if name == "sha2":
            blob = hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()
            if blob != entry["git_blob_sha"]:
                raise ValueError("Reference Git blob mismatch")
    return lock


def prepare(directory):
    # No extraction or deletion. Never replace an existing directory/file.
    directory.mkdir(exist_ok=False)
    lock = json.loads((ROOT / "REFERENCE_RUNTIME.lock.json").read_text(encoding="utf-8"))
    archive = fetch(lock["dkjson"]["url"])
    if hashlib.md5(archive).hexdigest() != lock["dkjson"]["archive_md5"]:
        raise ValueError("Reference archive mismatch")
    with tarfile.open(fileobj=io.BytesIO(archive), mode="r:gz") as tar:
        members = [item for item in tar.getmembers() if item.isfile() and item.name.endswith("/dkjson.lua")]
        if len(members) != 1 or members[0].size > LIMIT:
            raise ValueError("Unsupported reference archive")
        data = tar.extractfile(members[0]).read(LIMIT + 1)
    (directory / "dkjson.lua").write_bytes(data)
    resource = json.loads(fetch(lock["sha2"]["url"]))
    if resource["sha"] != lock["sha2"]["git_blob_sha"]:
        raise ValueError("Unsupported reference blob")
    (directory / "sha2.lua").write_bytes(base64.b64decode(resource["content"], validate=False))
    verify_reference(directory)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=pathlib.Path)
    args = parser.parse_args()
    try:
        prepare(args.output.resolve())
    except Exception:
        raise SystemExit("FAIL: exact host reference preparation; partial owned directory preserved") from None
    print("PASS: exact host-only dkjson and KOReader SHA references prepared")
