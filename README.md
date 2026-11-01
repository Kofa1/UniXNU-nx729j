# RedMagic 8 Pro (NX729J) iPadOS port

Active target: iPadOS 27.0.1 (24A446), arm64e, XNU 12377.121.6.

This branch migrates NX729J configuration to UniXNU format 2 and wires the
27 source-storage/root-policy path from the pinned Sheng implementation. It
uses the NX729J SM8550 tree, 4 KiB UFS geometry, 16 GiB memory map, and its
UEFI package integration. Display, touch, Adreno, and 120 Hz are not enabled
in this first root candidate.

## Current evidence

- The format 2 NX729J 27 configuration resolves and assembles a separate build tree.
- The official package preflight resolves all 70 pinned 27 kernel patches.
- The UEFI integration patch applies to uefi-sheng commit
  `20ac23d5e0937106c2129303dfc931b3390ae660`.
- The pinned NX729J firmware DTS compiles to an 848,678-byte DTB; its SHA-256 is
  `7541fab760d9f466d7565fc7ac0d3c30c52dec8c284ed9b72c12208b6f84376d`.
- The 27 signed OS and SystemOS policy headers match the pinned profile and share
  the same trust anchor.

These checks do not show a kernel build, root mount, `launchd`, PAC on the
phone, or a boot image. BOOTB-20 through BOOTB-23 remain iOS 17 no-root
diagnostics; retain them as references and do not repeat them.

## Build

The packaged root path uses Apple's public IOStorageFamily sources and Xcode,
so run the package workflow on macOS:

1. Add the stable 8-hex-digit software identity seed as the repository secret
   `UNIXNU_UNIQUE_CHIP_ID`.
2. In GitHub, open Actions > package > Run workflow on this branch with OS profile 27.
3. Keep the generated boot image, payload, kernel, and manifest together. The
   workflow retains its artifacts for one day.

For a local macOS checkout, follow UniXNU's [building guide](https://unixnu.com/building)
and [NX729J porting record](PORTING-NX729J.md). Run
`scripts/package.sh --check --no-deps --os 27` before a package build.

## Next device milestone

After a concrete package exists, boot that exact image once and report whether
the kernel publishes OS/SystemOS, mounts the configured root, and starts
`launchd`. Do not flash a userdata image until its layout and recovery route
have been reviewed. Then bring up display/touch at 60 Hz, followed by Adreno
rendering and measured 120 Hz presentation.
