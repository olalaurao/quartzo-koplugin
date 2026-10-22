"""Package only the bootstrap plugin; never install or replace a device file."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import zipfile


ROOT = Path(__file__).resolve().parents[2]
FILES = ("quartzo.koplugin/_meta.lua", "quartzo.koplugin/main.lua",
         "quartzo.koplugin/quartzo/statistics.lua")


def package(output, root=ROOT):
    output = Path(output)
    if output.suffix != ".zip":
        raise ValueError("output must be a fresh .zip file")
    contents = {}
    for name in FILES:
        source = root / name
        if source.is_symlink() or not source.is_file():
            raise ValueError("plugin source must be a regular file")
        contents[name] = source.read_bytes()
    buffer = io.BytesIO()
    # Two tiny files: storing them avoids zlib-version-dependent archive bytes.
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_STORED) as archive:
        for name, data in contents.items():
            entry = zipfile.ZipInfo(name, date_time=(2026, 10, 21, 0, 0, 0))
            entry.create_system = 3
            entry.external_attr = 0o100644 << 16
            entry.compress_type = zipfile.ZIP_STORED
            archive.writestr(entry, data)
    data = buffer.getvalue()
    with output.open("xb") as handle:
        handle.write(data)
    return {
        "sha256": hashlib.sha256(data).hexdigest(),
        "bytes": len(data),
        "files": {name: hashlib.sha256(value).hexdigest()
                  for name, value in contents.items()},
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(package(args.output), sort_keys=True))
