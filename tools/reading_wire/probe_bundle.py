"""Prepare/install/collect the single-use offline codec probe. Never attest hardware."""
import argparse
import hashlib
import json
import pathlib
import re
import secrets
import shutil
import subprocess

ROOT = pathlib.Path(__file__).resolve().parents[2]
NAME = "quartzo-wire-probe"
BASELINE = "v2026.07.1"
SOURCE_MAP = {
    "codec.lua": "tools/reading_wire/codec.lua",
    "koreader_deps.lua": "tools/reading_wire/koreader_deps.lua",
    "probe.lua": "tools/reading_wire/probe.lua",
    "kindle.lua": "tools/reading_wire/probe_kindle.lua",
    "run.sh": "tools/transport_probe/run.sh",
    "menu.json": "tools/reading_wire/probe_menu.json",
    "config.xml": "tools/reading_wire/probe_config.xml",
    "wire-vectors.json": "tools/reading_wire/upstream/transport_vectors.json",
    "dart-reference.json": "tools/reading_wire/dart_reference.json",
}
METADATA = {"bundle-manifest.json", "public-session.json"}
RUNTIME = {"run.lock", "launcher-status.txt", "device-observation.json", "device-observation.json.tmp"}
NATIVE = {"dkjson": "common/dkjson.lua", "sha2": "ffi/sha2.lua"}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def hexadecimal(value, size):
    return isinstance(value, str) and re.fullmatch(r"[a-f0-9]{" + str(size) + "}", value) is not None


def plain_root(path):
    path = pathlib.Path(path).absolute()
    for parent in (path, *path.parents):
        if parent.is_symlink() or parent.is_junction():
            raise ValueError("Linked probe path refused")
    return path.resolve(strict=True)


def read(path, limit):
    path = pathlib.Path(path)
    plain_root(path.parent)
    if path.is_symlink() or path.is_junction() or not path.is_file() or path.stat().st_size > limit:
        raise ValueError("Unsupported bounded probe file")
    with path.open("rb") as stream:
        value = stream.read(limit + 1)
    if len(value) > limit:
        raise ValueError("Probe file exceeds bound")
    return value


def parse(data):
    def pairs(items):
        value = {}
        for key, item in items:
            if key in value:
                raise ValueError("Duplicate probe metadata key")
            value[key] = item
        return value
    value = json.loads(data, object_pairs_hook=pairs)
    if not isinstance(value, dict):
        raise ValueError("Probe metadata object required")
    return value


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def read_sources(revision):
    if not hexadecimal(revision, 40):
        raise ValueError("Exact committed probe source required")
    resolved = subprocess.run(["git", "rev-parse", revision + "^{commit}"], cwd=ROOT, capture_output=True, check=True).stdout.decode().strip()
    if resolved != revision:
        raise ValueError("Probe commit mismatch")
    values = {}
    for name, source in SOURCE_MAP.items():
        value = subprocess.run(["git", "show", revision + ":" + source], cwd=ROOT, capture_output=True, check=True).stdout
        if name == "run.sh":
            if value.count(b"quartzo-transport-probe") != 1:
                raise ValueError("Unsupported launcher template")
            value = value.replace(b"quartzo-transport-probe", NAME.encode("ascii"))
        if len(value) > 65536 or b"\r" in value:
            raise ValueError("Unsupported probe source bytes")
        values[name] = value
    return values


def prepare(output, revision):
    output = pathlib.Path(output).absolute()
    plain_root(output.parent)
    if output.exists() or output.is_symlink() or output.is_junction():
        raise ValueError("Fresh probe bundle required")
    values = read_sources(revision)
    manifest = dict(probe_version=1, run_id=secrets.token_hex(16), koreader_baseline=BASELINE,
                    source_commit=revision, files={name: sha(value) for name, value in values.items()})
    manifest_bytes = encoded(manifest)
    session = dict(probe_version=1, run_id=manifest["run_id"], manifest_digest=sha(manifest_bytes))
    output.mkdir(exist_ok=False)
    for name, value in {**values, "bundle-manifest.json": manifest_bytes, "public-session.json": encoded(session)}.items():
        with (output / name).open("xb") as stream:
            stream.write(value)
    verify_bundle(output)
    return manifest


def verify_bundle(directory, allow_runtime=False):
    directory = plain_root(directory)
    expected = set(SOURCE_MAP) | METADATA
    actual = {entry.name for entry in directory.iterdir()}
    if not expected <= actual or actual - expected - (RUNTIME if allow_runtime else set()):
        raise ValueError("Unexpected probe bundle entry")
    for name in actual:
        path = directory / name
        if path.is_symlink() or path.is_junction():
            raise ValueError("Linked probe entry refused")
        if name == "run.lock":
            if not path.is_dir() or any(path.iterdir()):
                raise ValueError("Unsupported launcher lock")
        elif not path.is_file():
            raise ValueError("Regular probe file required")
    manifest_bytes = read(directory / "bundle-manifest.json", 8192)
    manifest = parse(manifest_bytes)
    if (set(manifest) != {"probe_version", "run_id", "koreader_baseline", "source_commit", "files"}
        or type(manifest["probe_version"]) is not int or manifest["probe_version"] != 1
        or not hexadecimal(manifest["run_id"], 32) or manifest["koreader_baseline"] != BASELINE
        or not isinstance(manifest["files"], dict) or set(manifest["files"]) != set(SOURCE_MAP)):
        raise ValueError("Unsupported probe manifest")
    sources = read_sources(manifest["source_commit"])
    for name, source in sources.items():
        value = read(directory / name, 65536)
        if value != source or sha(value) != manifest["files"][name]:
            raise ValueError("Probe source bytes changed")
    session = parse(read(directory / "public-session.json", 1024))
    if encoded(session) != encoded(dict(probe_version=1, run_id=manifest["run_id"], manifest_digest=sha(manifest_bytes))):
        raise ValueError("Probe session mismatch")
    return manifest, sha(manifest_bytes)


def native_snapshot(root):
    root = plain_root(root)
    if read(root / "koreader/git-rev", 64).decode().strip() != BASELINE:
        raise ValueError("Mounted KOReader baseline differs")
    runtime = root / "koreader/luajit"
    if runtime.is_symlink() or runtime.is_junction() or not runtime.is_file():
        raise ValueError("KOReader runtime missing")
    values = {key: sha(read(root / "koreader" / name, 1048576)) for key, name in NATIVE.items()}
    return values


def install(bundle, root):
    bundle, root = plain_root(bundle), plain_root(root)
    manifest, manifest_digest = verify_bundle(bundle)
    native = native_snapshot(root)
    extensions = plain_root(root / "extensions")
    if extensions.parent != root or shutil.disk_usage(root).free < 4 * 1024 * 1024:
        raise ValueError("Mounted test target unavailable or too little space")
    target = extensions / NAME
    if target.exists() or target.is_symlink() or target.is_junction():
        raise ValueError("Existing diagnostic is preserved")
    target.mkdir(exist_ok=False)
    for name in set(SOURCE_MAP) | METADATA:
        with (target / name).open("xb") as stream:
            stream.write(read(bundle / name, 65536))
    if verify_bundle(target) != (manifest, manifest_digest) or native_snapshot(root) != native:
        raise ValueError("Installed probe or runtime changed")
    return dict(probe_version=1, run_id=manifest["run_id"], manifest_digest=manifest_digest,
                source_commit=manifest["source_commit"], koreader_version=BASELINE,
                native_source_sha256=native, canonical_ack=False, production_changed=False)


def collect(bundle, root, observation):
    manifest, manifest_digest = verify_bundle(bundle)
    root = plain_root(root)
    target = root / "extensions" / NAME
    if verify_bundle(target, allow_runtime=True) != (manifest, manifest_digest):
        raise ValueError("Installed probe differs from prepared source")
    expected = dict(probe_version=1, run_id=manifest["run_id"], manifest_digest=manifest_digest,
                    source_commit=manifest["source_commit"], koreader_version=BASELINE,
                    native_source_sha256=native_snapshot(root), canonical_ack=False, production_changed=False)
    if encoded(parse(read(observation, 4096))) != encoded(expected):
        raise ValueError("Installation observation no longer matches")
    if read(target / "launcher-status.txt", 64).strip() != b"completed" or not (target / "run.lock").is_dir():
        raise ValueError("Single-use launcher did not complete")
    if (target / "device-observation.json.tmp").exists():
        raise ValueError("Unfinished device report remains")
    device = parse(read(target / "device-observation.json", 8192))
    required = {"probe_version": 1, "phase": "passed", "source_data": "synthetic", "uses_synthetic_clock": True,
        "canonical_ack": False, "canonical_persistence_proven": False, "statistics_accessed": False,
        "source_cursor_changed": False, "network_accessed": False, "wifi_changed": False,
        "golden_checks": 3, "negative_cases": 12, "native_reference_cases": 5,
        "conflicting_positions": 3, "isolated_entries": 3, "expired_request_rejected": True,
        "run_id": manifest["run_id"], "manifest_digest": manifest_digest, "source_commit": manifest["source_commit"],
        "lua_version": "Lua 5.1", "jit_arch": "arm", "koreader_version": BASELINE,
        "native_source_sha256": expected["native_source_sha256"]}
    if set(device) != set(required) | {"jit_version", "json_version", "cpu_seconds"}:
        raise ValueError("Unexpected device report fields")
    for key, value in required.items():
        if type(device[key]) is not type(value) or device[key] != value:
            raise ValueError("Device compatibility check missing or mismatched")
    if (not isinstance(device["jit_version"], str) or not re.fullmatch(r"LuaJIT 2\.1[ A-Za-z0-9.()_-]{0,96}", device["jit_version"])
        or not isinstance(device["json_version"], str) or not re.fullmatch(r"dkjson [0-9]+\.[0-9]+", device["json_version"])
        or type(device["cpu_seconds"]) not in (int, float) or not 0 <= device["cpu_seconds"] < 120):
        raise ValueError("Device runtime metadata unsupported")
    # Matching synthetic observations alone cannot establish physical origin.
    return dict(probe_version=1, proof="correlated_offline_wire_observations", source_data="synthetic",
                source_commit=manifest["source_commit"], run_id=manifest["run_id"], observations_match=True,
                physical_execution_attested=False, canonical_ack=False, canonical_persistence_proven=False,
                source_cursor_changed=False, production_changed=False, source_sha256=manifest["files"],
                native_source_sha256=expected["native_source_sha256"], runtime={key: device[key] for key in
                    ("lua_version", "jit_version", "jit_arch", "json_version", "koreader_version", "cpu_seconds")})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    prepare_parser = commands.add_parser("prepare")
    prepare_parser.add_argument("--output", type=pathlib.Path, required=True)
    prepare_parser.add_argument("--source-commit", required=True)
    install_parser = commands.add_parser("install")
    collect_parser = commands.add_parser("collect")
    for command in (install_parser, collect_parser):
        command.add_argument("--bundle", type=pathlib.Path, required=True)
        command.add_argument("--kindle-root", type=pathlib.Path, required=True)
        command.add_argument("--observation", type=pathlib.Path, required=True)
    collect_parser.add_argument("--output", type=pathlib.Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == "prepare":
            prepare(args.output, args.source_commit)
        else:
            destination = args.observation if args.command == "install" else args.output
            plain_root(destination.absolute().parent)
            if destination.exists() or destination.is_symlink() or destination.is_junction():
                raise ValueError("Fresh host observation path required")
            report = install(args.bundle, args.kindle_root) if args.command == "install" else collect(args.bundle, args.kindle_root, args.observation)
            with destination.open("xb") as stream:
                stream.write(encoded(report))
        print("Offline diagnostic operation completed; no canonical ACK or physical attestation inferred")
    except Exception:
        raise SystemExit("FAIL: offline diagnostic operation; existing and partial files preserved") from None


if __name__ == "__main__":
    main()
