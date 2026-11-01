#!/usr/bin/env python3
"""Check the NX729J iPadOS 27 firmware handoff and root-policy inputs."""
from pathlib import Path
import hashlib
import json
import os
import tomllib

TREE = Path(__file__).resolve().parents[1]
UEFI_VALUE = os.environ.get("UNIXNU_UEFI")
if not UEFI_VALUE:
    raise SystemExit("UNIXNU_UEFI is unset; invoke through unixnu build firmware")
UEFI = Path(UEFI_VALUE).resolve()
DSC = UEFI / "Platforms/ZTE/nx729jPkg/nx729j.dsc"
FDF = UEFI / "Platforms/ZTE/nx729jPkg/nx729j.fdf"
if not DSC.is_file() or not FDF.is_file():
    raise SystemExit(f"not an NX729J uefi-sheng checkout: {UEFI}")
dsc, fdf = DSC.read_text(errors="replace"), FDF.read_text(errors="replace")
for marker in ("UniXNU.inf", "UniXNUDxe.inf", "DarwinBoot.inf", "UniXNURamDiskDxe.inf"):
    if marker not in dsc or marker not in fdf:
        raise SystemExit(f"UEFI integration is missing {marker}")
config = UEFI / "Resources/Configs/nx729j.toml"
if not config.is_file():
    raise SystemExit(f"missing {config}")
with config.open("rb") as handle:
    fd_size = tomllib.load(handle).get("uefi_fd", {}).get("size")
if not fd_size:
    raise SystemExit("NX729J UEFI config has no FD size")
memory_map = UEFI / "Platforms/ZTE/nx729jPkg/Library/MemoryMapLib/MemoryMapLib.c"
if not memory_map.is_file():
    raise SystemExit("NX729J UEFI memory-map source is missing")

dtb = TREE / "build/nx729j/nx729j.dtb"
if not dtb.is_file() or b"cont_splash_region" not in dtb.read_bytes():
    raise SystemExit("NX729J firmware DTB is missing or lacks the stock splash reservation")

policy_root = TREE / "scripts/policies/ipados-27.0.1-24A446"
key_digest = None
for name, expected_uuid in (("OS", "2F8E6EED-68D5-4261-B8A3-12571BAA2DD4"),
                            ("SystemOS", "F914C62A-AD00-47C6-8281-5746291C339A")):
    directory = policy_root / name
    header = (directory / "manifest.header.bin").read_bytes()
    key = (directory / "trusted-key.bin").read_bytes()
    verification = json.loads((directory / "verification.json").read_text())
    if len(header) != 544 or header[:8] != b"VROOT01\0":
        raise SystemExit(f"{name}: invalid signed policy header")
    if len(key) != 395 or key[:8] != b"VROOTKEY":
        raise SystemExit(f"{name}: invalid root trust anchor")
    if verification.get("real_c_signature_and_block_verification") is not True:
        raise SystemExit(f"{name}: image verification record is incomplete")
    if verification.get("volume_uuid") != expected_uuid:
        raise SystemExit(f"{name}: unexpected root volume UUID")
    if verification.get("image_sha256") != header[56:88].hex():
        raise SystemExit(f"{name}: policy header image digest mismatch")
    digest = hashlib.sha256(key).hexdigest()
    if verification.get("trusted_key_sha256") != digest:
        raise SystemExit(f"{name}: trust anchor digest mismatch")
    if key_digest is not None and key_digest != digest:
        raise SystemExit("OS and SystemOS policies use different trust anchors")
    key_digest = digest

print(f"NX729J UEFI modules and iPadOS 27 root policy headers are consistent (FD {fd_size:#x})")
print("This preflight does not qualify controller access, root mount, launchd, or device PAC.")
