"""Prepare/install/collect a fresh single-use diagnostic extension, never a plugin."""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import re
import tempfile
import time

from host import PAYLOAD, private_address

NAME = "quartzo-transport-probe"
BASELINE = "v2026.07.1"
SOURCES = ("client.lua", "device.lua", "kindle.lua", "run.sh", "menu.json", "config.xml")
RUNTIME = ("private-session.json", "server.pem", "untrusted.pem", "synthetic-payload.json")


def read_json(path, limit=8192):
    if path.is_symlink():
        raise ValueError("Linked diagnostic input refused")
    with path.open("rb") as stream:
        value = stream.read(limit + 1)
    if len(value) > limit:
        raise ValueError("Diagnostic input exceeds bound")
    def pairs(items):
        result = {}
        for key, item in items:
            if key in result: raise ValueError("Duplicate diagnostic JSON key")
            result[key] = item
        return result
    return json.loads(value, object_pairs_hook=pairs)


def owned_temp(path):
    path = pathlib.Path(path)
    if path.is_symlink(): raise ValueError("Linked runtime refused")
    path = path.resolve()
    if not path.is_relative_to(pathlib.Path(tempfile.gettempdir()).resolve()):
        raise ValueError("Private bundles must stay inside OS temporary storage")
    if any((parent / ".git").exists() for parent in (path, *path.parents)):
        raise ValueError("Private bundles must stay outside Git")
    return path


def prepare(session, output):
    session, output = owned_temp(session), owned_temp(output)
    if output.exists(): raise ValueError("Fresh output directory required")
    config = read_json(session / "private-session.json", 2048)
    if set(config) != {"endpoint", "token", "expired_token", "run_id", "expires_at", "ca_file", "bad_ca_file"}:
        raise ValueError("Unexpected session fields")
    match = re.fullmatch(r"https://([0-9.]+):([0-9]+)", config["endpoint"])
    if not match or not 1024 <= int(match[2]) <= 65535:
        raise ValueError("Explicit private HTTPS endpoint required")
    private_address(match[1])
    for name, size in (("token", 64), ("expired_token", 64), ("run_id", 32)):
        if not isinstance(config[name], str) or not re.fullmatch(f"[a-f0-9]{{{size}}}", config[name]):
            raise ValueError("Invalid synthetic session identity")
    if config["token"] == config["expired_token"] or not 30 < config["expires_at"] - time.time() <= 1800:
        raise ValueError("Expired or invalid synthetic session")
    if config["ca_file"] != "server.pem" or config["bad_ca_file"] != "untrusted.pem":
        raise ValueError("Unexpected trust paths")
    values = {}
    for name in RUNTIME:
        path = session / name
        if path.is_symlink(): raise ValueError("Linked runtime input refused")
        with path.open("rb") as stream: value = stream.read(16385)
        if len(value) > 16384: raise ValueError("Runtime input exceeds bound")
        if name.endswith(".pem") and (b"-----BEGIN CERTIFICATE-----" not in value or b"PRIVATE KEY" in value):
            raise ValueError("Only public diagnostic certificates may leave host")
        values[name] = value
    if values["synthetic-payload.json"] != PAYLOAD:
        raise ValueError("Only the exact synthetic payload is permitted")
    for name in SOURCES:
        # Normalize only repository source line endings for the Unix device.
        source = (pathlib.Path(__file__).resolve().parents[2] / "quartzo.koplugin/quartzo/transport.lua"
                  if name == "client.lua" else pathlib.Path(__file__).with_name(name))
        values[name] = source.read_bytes().replace(b"\r\n", b"\n")
    manifest = dict(probe_version=1, run_id=config["run_id"], koreader_baseline=BASELINE,
        source_data="synthetic", files={name: hashlib.sha256(value).hexdigest() for name, value in values.items()})
    output.mkdir(mode=0o700, exist_ok=False)
    for name, value in values.items(): (output / name).write_bytes(value)
    (output / "bundle-manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def verify_bundle(directory):
    manifest = read_json(directory / "bundle-manifest.json")
    expected = set(SOURCES + RUNTIME)
    if (manifest.get("probe_version") != 1 or manifest.get("koreader_baseline") != BASELINE
        or set(manifest.get("files", {})) != expected):
        raise ValueError("Unexpected bundle manifest")
    for name in expected:
        path = directory / name
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 32768:
            raise ValueError("Invalid bundle file")
        if hashlib.sha256(path.read_bytes()).hexdigest() != manifest["files"][name]:
            raise ValueError("Bundle bytes changed")
    return manifest


def install(bundle, kindle_root):
    bundle, root = owned_temp(bundle), pathlib.Path(kindle_root).resolve()
    verify_bundle(bundle)
    if (root / "koreader" / "git-rev").read_text().strip() != BASELINE:
        raise ValueError("Mounted KOReader baseline mismatch")
    if not (root / "koreader" / "luajit").is_file():
        raise ValueError("Mounted KOReader runtime missing")
    extensions = root / "extensions"
    if not extensions.is_dir() or extensions.is_symlink():
        raise ValueError("Existing plain KUAL extensions directory required")
    target = extensions / NAME
    if target.exists() or target.is_symlink():
        raise ValueError("Existing diagnostic extension will never be overwritten")
    # Only this fresh owned extension is created. No recursive device deletion.
    target.mkdir(exist_ok=False)
    for name in SOURCES + RUNTIME + ("bundle-manifest.json",):
        with (target / name).open("xb") as stream: stream.write((bundle / name).read_bytes())
    verify_bundle(target)
    return target


def collect(bundle, kindle_root, host_report):
    bundle = owned_temp(bundle)
    manifest = verify_bundle(bundle)
    device_directory = pathlib.Path(kindle_root).resolve() / "extensions" / NAME
    if verify_bundle(device_directory) != manifest:
        raise ValueError("Installed diagnostic does not match prepared bytes")
    device = read_json(device_directory / "device-observation.json", 4096)
    host = read_json(pathlib.Path(host_report))
    if not (device_directory / "launcher-status.txt").read_text().strip() == "completed":
        raise ValueError("Single-use device launcher did not complete")
    if host.get("run_id") != manifest["run_id"] or device.get("run_id") != manifest["run_id"]:
        raise ValueError("Host/device run identities do not agree")
    required = ("bad_ca_rejected", "unauthorized_rejected", "expired_token_rejected",
        "rate_limit_retried", "server_error_retried", "replay_receipt_received")
    if (device.get("phase") != "passed" or device.get("request_attempts") != 9
        or device.get("lua_version") != "Lua 5.1" or device.get("luasec_version") != "1.3.2"
        or device.get("koreader_version") != BASELINE
        or any(device.get(key) is not True for key in required)):
        raise ValueError("Device diagnostic incomplete or runtime differs")
    for flag in ("canonical_ack_claimed", "canonical_persistence_proven", "statistics_accessed", "wifi_changed"):
        if device.get(flag) is not False: raise ValueError("Unexpected device effect claim")
    if (host.get("proof") != "host_tls_fixture_only" or host.get("source_data") != "synthetic"
        or host.get("counts") != dict(unauthorized=1, expired=1, rate=1, server=1, ok=4)
        or host.get("unique_payloads") != 1 or host.get("tls_versions") != ["TLSv1.2"]
        or host.get("server_errors") != 0
        or host.get("canonical_ack_claimed") is not False
        or host.get("canonical_persistence_proven") is not False
        or host.get("kindle_runtime_proven") is not False):
        raise ValueError("Host diagnostic sequence does not agree")
    # Whitelist output. Input observations alone cannot attest physical origin.
    return dict(probe_version=1, proof="correlated_synthetic_transport_observations",
        run_id=manifest["run_id"], source_data="synthetic", observations_match=True,
        physical_execution_attested=False, canonical_ack_claimed=False,
        canonical_persistence_proven=False, source_hashes={key: manifest["files"][key] for key in SOURCES},
        request_attempts=9, tls_versions=["TLSv1.2"], koreader_version=BASELINE)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    prepare_parser = commands.add_parser("prepare")
    prepare_parser.add_argument("--session", required=True, type=pathlib.Path)
    prepare_parser.add_argument("--output", required=True, type=pathlib.Path)
    install_parser = commands.add_parser("install")
    collect_parser = commands.add_parser("collect")
    for command in (install_parser, collect_parser):
        command.add_argument("--bundle", required=True, type=pathlib.Path)
        command.add_argument("--kindle-root", required=True, type=pathlib.Path)
    collect_parser.add_argument("--host-report", required=True, type=pathlib.Path)
    collect_parser.add_argument("--output", required=True, type=pathlib.Path)
    args = parser.parse_args()
    try:
        if args.command == "prepare": prepare(args.session, args.output)
        elif args.command == "install": install(args.bundle, args.kindle_root)
        else:
            report = collect(args.bundle, args.kindle_root, args.host_report)
            with args.output.open("x", encoding="utf-8") as stream: json.dump(report, stream, indent=2)
        print("Diagnostic operation completed; no canonical ACK or physical attestation inferred")
    except Exception as error:
        # Do not print runtime paths, JSON or credential-bearing exceptions.
        print("Diagnostic operation failed: " + type(error).__name__)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
