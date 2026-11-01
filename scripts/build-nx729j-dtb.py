#!/usr/bin/env python3
"""Compile the pinned NX729J handoff device tree for firmware and boot-image assembly."""
from pathlib import Path
import hashlib
import os
import shutil
import subprocess
import tempfile

TREE = Path(__file__).resolve().parents[1]
PACKAGE_CANDIDATES = (TREE / "kits/nx729j/firmware/nx729j.dts",
                      TREE / "package/firmware/nx729j.dts")
source = next((p for p in PACKAGE_CANDIDATES if p.is_file()), None)
if source is None:
    raise SystemExit("NX729J DTS is missing from the resolved device package")
uefi_value = os.environ.get("UNIXNU_UEFI")
if not uefi_value:
    raise SystemExit("UNIXNU_UEFI is unset; invoke through unixnu build firmware")
uefi = Path(uefi_value).resolve()
if not (uefi / "Platforms/ZTE/nx729jPkg/nx729j.dsc").is_file():
    raise SystemExit(f"not an NX729J uefi-sheng checkout: {uefi}")

outputs = (TREE / "build/nx729j/nx729j.dtb", uefi / "Resources/DTBs/nx729j.dtb")
for output in outputs:
    output.parent.mkdir(parents=True, exist_ok=True)
fd, temp_name = tempfile.mkstemp(prefix="nx729j-", suffix=".dtb", dir=outputs[0].parent)
os.close(fd)
temp = Path(temp_name)
try:
    result = subprocess.run(["dtc", "-I", "dts", "-O", "dtb", "-o", str(temp), str(source)],
                            text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if result.returncode:
        raise SystemExit("dtc failed:\n" + result.stdout[-5000:])
    built = temp.read_bytes()
    if not built:
        raise SystemExit("dtc produced an empty NX729J DTB")
    digest = hashlib.sha256(built).hexdigest()
    for output in outputs:
        if output.exists():
            if hashlib.sha256(output.read_bytes()).hexdigest() != digest:
                raise SystemExit(f"refusing to replace different device tree: {output}")
        else:
            shutil.copyfile(temp, output)
    print(f"NX729J DTB {len(built)} bytes sha256 {digest}")
finally:
    temp.unlink(missing_ok=True)
