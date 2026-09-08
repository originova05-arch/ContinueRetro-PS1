"""Package only the source-recovery helper after CI tests; never package the app/ROM."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import zipfile


def build(output: Path, validation_log: Path) -> Path:
    source = Path(__file__).resolve().parent
    names = {"source_bridge.py": "source_bridge.py", "test_source_bridge.py": "test_source_bridge.py",
             "PREPARE_STUDIO_SOURCE.command": "PREPARE_STUDIO_SOURCE.command",
             "SOURCE_BRIDGE_README_TH.md": "README_TH.md"}
    files = {target: (source / name).read_bytes() for name, target in names.items()}
    log = validation_log.read_bytes()
    if len(log) > 2 * 1024 * 1024 or b"\nOK\n" not in log:
        raise ValueError("A bounded successful unittest log is required; packaging is not a test substitute")
    files["VALIDATION.txt"] = log
    files["BUILD_INFO.json"] = (json.dumps({
        "helper_version": "1", "source_commit": os.environ.get("GITHUB_SHA", "local-unrecorded"),
        "ci_run": os.environ.get("GITHUB_RUN_ID"), "tests": "authored ZIP fixtures + isolated quality tests",
        "real_v060_zip_inspected_in_ci": False, "london_tested": False, "native_mac_tested": False,
        "app_updater": False, "models_trained": False,
    }, indent=2) + "\n").encode()
    files["PACKAGE_MANIFEST.sha256"] = ("\n".join(
        f"{hashlib.sha256(data).hexdigest()}  {name}" for name, data in sorted(files.items())
    ) + "\n").encode()
    output.mkdir(parents=True, exist_ok=True)
    destination = output / "ContinueRetro_Source_Bridge_v1.zip"
    with zipfile.ZipFile(destination, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, data in sorted(files.items()):
            info = zipfile.ZipInfo("ContinueRetro_Source_Bridge_v1/" + name, date_time=(2026, 9, 8, 0, 0, 0))
            info.create_system = 3
            info.external_attr = (stat.S_IFREG | (0o755 if name.endswith(".command") else 0o644)) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, data)
    with zipfile.ZipFile(destination) as archive:
        if archive.testzip() is not None:
            raise ValueError("Generated helper ZIP failed CRC validation")
        for name, data in files.items():
            if archive.read("ContinueRetro_Source_Bridge_v1/" + name) != data:
                raise ValueError("Packaged file differs from tested source")
    sha = hashlib.sha256(destination.read_bytes()).hexdigest()
    destination.with_suffix(".zip.sha256").write_text(f"{sha}  {destination.name}\n", encoding="ascii")
    print(f"HELPER_PACKAGE={destination.name}")
    print(f"HELPER_SHA256={sha}")
    print("SCOPE=source-recovery helper; no Studio installation, no model/game validation")
    return destination


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-directory", type=Path, required=True)
    parser.add_argument("--validation-log", type=Path, required=True)
    args = parser.parse_args()
    build(args.output_directory, args.validation_log)
