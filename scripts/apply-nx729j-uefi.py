#!/usr/bin/env python3
"""Apply the pinned NX729J UniXNU module integration to the selected UEFI checkout."""
from pathlib import Path
import os
import subprocess
import sys

HERE = Path(__file__).resolve().parent
DEVICE = HERE.parent if HERE.name == "scripts" else HERE
PATCHES = [DEVICE / "firmware/patches/nx729j-unixnu-integration.patch", DEVICE / "package/firmware/patches/nx729j-unixnu-integration.patch",
           DEVICE / "kits/nx729j/firmware/patches/nx729j-unixnu-integration.patch"]
patch = next((path for path in PATCHES if path.is_file()), None)
uefi_value = os.environ.get("UNIXNU_UEFI")
if not patch:
    raise SystemExit("NX729J UEFI patch is missing from the device package")
if not uefi_value:
    raise SystemExit("UNIXNU_UEFI is unset; invoke through unixnu build firmware")
uefi = Path(uefi_value).resolve()
if not (uefi / "Platforms/ZTE/nx729jPkg/nx729j.dsc").is_file():
    raise SystemExit(f"not an NX729J uefi-sheng checkout: {uefi}")
files = ["Platforms/ZTE/nx729jPkg/nx729j.dsc", "Platforms/ZTE/nx729jPkg/nx729j.fdf"]

def git(*args):
    return subprocess.run(["git", "-C", str(uefi), *args], capture_output=True, text=True)

already = git("apply", "--reverse", "--check", str(patch))
if already.returncode == 0:
    print("NX729J UEFI UniXNU integration is already applied")
    sys.exit(0)
status = git("status", "--porcelain", "--", *files)
if status.returncode or status.stdout.strip():
    raise SystemExit("refusing to patch modified UEFI DSC/FDF files; inspect the UEFI checkout first")
check = git("apply", "--check", str(patch))
if check.returncode:
    raise SystemExit("pinned NX729J UEFI patch does not apply:\n" + check.stderr)
apply = git("apply", str(patch))
if apply.returncode:
    raise SystemExit("failed to apply NX729J UEFI patch:\n" + apply.stderr)
print(f"Applied {patch.name} to {uefi}")
