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
import re
import shutil
import subprocess

TREE = Path(__file__).resolve().parents[1]
OUT = TREE / "build/sheng-source-storage"


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def weak_diag_defaults(source, builder):
    """Keep this fallback object independent of unrelated XNU kernel headers.

    BootDiagExport's optional weak symbols are mostly scalar/pointer declarations.
    Replaying all of its includes in a second translation unit pulls in IPC headers
    with incompatible BSD-private declaration paths. Only concrete struct arrays
    need their local element definitions; pointer-only struct types can stay opaque.
    """
    normalized = source.with_name(".BootDiagExportWeakDefaultsInput.c")
    normalized.write_text('\n'.join(
        line.split('//', 1)[0] if 'weak_import' in line else line
        for line in source.read_text().splitlines()) + '\n')
    try:
        generated = builder.weak_defaults(normalized).splitlines()
    finally:
        normalized.unlink(missing_ok=True)
    marker = '#pragma clang diagnostic ignored "-Wc23-extensions"'
    try:
        declarations = generated[generated.index(marker) + 1:]
    except ValueError as error:
        raise SystemExit("upstream weak-default generator output changed") from error

    text = source.read_text()
    complete = set(re.findall(r'^extern\s+struct\s+(\w+)\s+\w+\s*\[', text, re.M))
    referenced = set(re.findall(r'\bstruct\s+(\w+)', '\n'.join(declarations)))
    forwards = [f'struct {name};' for name in sorted(referenced - complete)]
    definitions = []
    for name in sorted(complete):
        start = re.search(rf'\bstruct\s+{re.escape(name)}\s*\{{', text)
        if not start:
            raise SystemExit(f"missing local definition for weak array element struct {name}")
        opening = text.find('{', start.start())
        depth = 0
        end = None
        for index in range(opening, len(text)):
            if text[index] == '{':
                depth += 1
            elif text[index] == '}':
                depth -= 1
                if depth == 0:
                    end = index + 1
                    while end < len(text) and text[end].isspace():
                        end += 1
                    if end < len(text) and text[end] == ';':
                        end += 1
                    break
        if end is None:
            raise SystemExit(f"unterminated local definition for struct {name}")
        definitions.append(text[start.start():end].strip())
    return '\n'.join(['#include <stdint.h>', *forwards, *definitions, marker, *declarations]) + '\n'


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
    generated.write_text(weak_diag_defaults(source, builder))
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
