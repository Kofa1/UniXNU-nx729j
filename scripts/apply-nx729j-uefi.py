#!/usr/bin/env python3
"""Apply the pinned NX729J UniXNU integration and memory reservations to UEFI."""
from pathlib import Path
import os
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
DEVICE = HERE.parent if HERE.name == "scripts" else HERE
INTEGRATION_PATCHES = [DEVICE / "firmware/patches/nx729j-unixnu-integration.patch", DEVICE / "package/firmware/patches/nx729j-unixnu-integration.patch",
                       DEVICE / "kits/nx729j/firmware/patches/nx729j-unixnu-integration.patch",
                       DEVICE / "kits/sheng/firmware/patches/nx729j-unixnu-integration.patch"]
integration_patch = next((path for path in INTEGRATION_PATCHES if path.is_file()), None)
patches = [] if integration_patch is None else [
    (integration_patch, ["Platforms/ZTE/nx729jPkg/nx729j.dsc", "Platforms/ZTE/nx729jPkg/nx729j.fdf"]),
    (integration_patch.with_name("nx729j-memory-map.patch"),
     ["Platforms/ZTE/nx729jPkg/Library/MemoryMapLib/MemoryMapLib.c"]),
]
uefi_value = os.environ.get("UNIXNU_UEFI")
if not integration_patch:
    raise SystemExit("NX729J UEFI integration patch is missing from the device package")
missing = [str(path) for path, _ in patches if not path.is_file()]
if missing:
    raise SystemExit("NX729J UEFI patch set is incomplete: " + ", ".join(missing))
if not uefi_value:
    raise SystemExit("UNIXNU_UEFI is unset; invoke through unixnu build firmware")
uefi = Path(uefi_value).resolve()
if not (uefi / "Platforms/ZTE/nx729jPkg/nx729j.dsc").is_file():
    raise SystemExit(f"not an NX729J uefi-sheng checkout: {uefi}")
def git(*args):
    return subprocess.run(["git", "-C", str(uefi), *args], capture_output=True, text=True)

with tempfile.TemporaryDirectory(prefix="nx729j-uefi-patch-") as temp_dir:
    for patch, files in patches:
        patch_for_git = Path(temp_dir) / patch.name
        patch_bytes = patch.read_bytes()
        target_files = [uefi / name for name in files]
        if any(b"\r\n" in path.read_bytes() for path in target_files):
            patch_bytes = patch_bytes.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
        patch_for_git.write_bytes(patch_bytes)

        already = git("apply", "--reverse", "--check", str(patch_for_git))
        if already.returncode == 0:
            print(f"NX729J UEFI patch {patch.name} is already applied")
            continue
        status = git("status", "--porcelain", "--", *files)
        if status.returncode or status.stdout.strip():
            raise SystemExit(f"refusing to patch modified UEFI files for {patch.name}; inspect the UEFI checkout first")
        check = git("apply", "--check", str(patch_for_git))
        if check.returncode:
            raise SystemExit(f"pinned NX729J UEFI patch {patch.name} does not apply:\n" + check.stderr)
        apply = git("apply", str(patch_for_git))
        if apply.returncode:
            raise SystemExit(f"failed to apply NX729J UEFI patch {patch.name}:\n" + apply.stderr)
        print(f"Applied {patch.name} to {uefi}")
