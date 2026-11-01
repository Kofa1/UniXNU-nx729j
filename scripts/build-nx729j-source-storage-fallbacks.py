#!/usr/bin/env python3
"""Provide link-time defaults for optional sheng diagnostics absent on NX729J.

The pinned source-storage recipe already makes optional BootLog imports weak,
but its iPadOS 27 BootDiagExport source also imports diagnostics that are not
built for this board. This adds hidden weak defaults so available providers win.
"""
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess

TREE = Path(__file__).resolve().parents[1]
OUT = TREE / "build/sheng-source-storage"


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    source = TREE / "kits/sheng/BootDiagExport.c"
    generated = OUT / "BootDiagExportWeakDefaults.c"
    object_file = OUT / "BootDiagExportWeakDefaults.o"
    command_file = OUT / "BootDiagExport.command.json"
    archive = OUT / "libShengSourceStorage.a"
    catalog_archive = TREE / "build/sheng-ufs/libShengUfs.a"
    if not all(path.is_file() for path in (source, command_file, archive)):
        raise SystemExit("source-storage build outputs are missing; run the upstream recipe first")

    builder = load("nx729j_source_storage_builder", TREE / "scripts/build-sheng-source-storage.py")
    generated.write_text(builder.weak_defaults(source))
    command = json.loads(command_file.read_text())
    source_indexes = [index for index, argument in enumerate(command)
                      if Path(argument).name == "BootDiagExport.c"]
    if len(source_indexes) != 1:
        raise SystemExit("could not locate BootDiagExport.c in its recorded compile command")
    command[source_indexes[0]] = str(generated)
    try:
        output_index = command.index("-o")
        command[output_index + 1] = str(object_file)
        dep_index = command.index("-MF")
        command[dep_index + 1] = str(object_file.with_suffix(".d"))
    except (ValueError, IndexError) as error:
        raise SystemExit("unexpected recorded BootDiagExport compile command") from error

    record_path = TREE / "build/xnu/ios-obj/DEVELOPMENT_ARM64_BCM2837/osfmk/DEVELOPMENT/startup.o.json"
    record = json.loads(record_path.read_text().strip().rstrip(","))
    subprocess.run(command, cwd=record["directory"], check=True)
    target = load("nx729j_kernel_target", TREE / "scripts/kernel_target.py")
    target.check_object(object_file.read_bytes(), object_file.name)
    subprocess.run(["xcrun", "ar", "rcs", str(archive), str(object_file)], check=True)
    catalog_archive.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(archive, catalog_archive)

    report_path = OUT / "report.json"
    report = json.loads(report_path.read_text())
    report.setdefault("sources", {})[str(generated)] = hashlib.sha256(generated.read_bytes()).hexdigest()
    report["archive_sha256"] = hashlib.sha256(archive.read_bytes()).hexdigest()
    report["nx729j_optional_bootdiag_defaults"] = str(object_file)
    report_path.write_text(json.dumps(report, indent=2) + "\n")
    print(archive)


if __name__ == "__main__":
    main()
