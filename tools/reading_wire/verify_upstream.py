"""Verify pinned bytes locally; --remote also compares the exact GitHub revision."""
import argparse
import base64
import hashlib
import json
import pathlib
import subprocess

ROOT = pathlib.Path(__file__).resolve().parent


def verify(remote=False):
    lock = json.loads((ROOT / "UPSTREAM.lock.json").read_text(encoding="utf-8"))
    if lock["repository"] != "olalaurao/aplicativo" or len(lock["sourceCommit"]) != 40:
        raise ValueError("Unsupported upstream identity")
    for name, entry in lock["files"].items():
        if pathlib.PurePosixPath(name).name != name or entry["path"] != "contracts/quartzo/reading_activity/" + name:
            raise ValueError("Unsupported upstream path")
        data = (ROOT / "upstream" / name).read_bytes()
        blob = hashlib.sha1(b"blob " + str(len(data)).encode("ascii") + b"\0" + data).hexdigest()
        if hashlib.sha256(data).hexdigest() != entry["sha256"] or blob != entry["gitBlobSha"]:
            raise ValueError("Pinned upstream byte mismatch")
        if remote:
            # gh uses its existing account credential; neither token nor decoder
            # errors are included in output. No local-source override exists.
            command = ["gh", "api", f"repos/{lock['repository']}/contents/{entry['path']}?ref={lock['sourceCommit']}"]
            result = subprocess.run(command, capture_output=True, timeout=90, check=True)
            value = json.loads(result.stdout)
            if value["sha"] != blob or base64.b64decode(value["content"]) != data:
                raise ValueError("Remote upstream byte mismatch")
    return len(lock["files"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--remote", action="store_true")
    args = parser.parse_args()
    try:
        count = verify(args.remote)
    except Exception:
        raise SystemExit("FAIL: pinned Reading wire verification") from None
    print(f"PASS: {count} pinned Reading files verified" + (" against GitHub" if args.remote else " locally"))
