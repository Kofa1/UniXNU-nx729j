# 适配进度：红魔 8 Pro+ 现在到哪一步了

最后更新：2026-11-03（本机 Xcode 内核与 prelink 映射推进）

## 2026-11-03 Sheng 启动结构与当前内核进度

- 本轮设备仓库更新基于提交 `a5aab9f76a627c6bb0b126b3cb34db4948081121`；分支为 `codex/ios27-interactive-port`。UniXNU 固定在 `474cfeeb4e35b3fc91ec98cd2bb54e1ab25389b8`；UEFI 固定在 `20ac23d5e0937106c2129303dfc931b3390ae660`。
- 已按 Sheng 的 SM8550 结构完成 NX729J 本地 host 构建：板级 archive、GOP legacy display、AppleKeyStoreState、HID/按键源对象、RELEASE-LTO 文件集参考、XNU 编译/链接及 iPadOS 27.0.1 kernelcache prelink 均通过。Adreno740 与 Sheng storage inputs 使用其现有生成流程；`vmm-present=1` 保留，未加 PMGR 假驱动。
- 内核文件：`UniXNU-sheng-reference/out/nx729j/ipados-27.0.1-24A446/nx729j_ipados27/kernel/kernel.macho`，96,190,464 字节。XNU 已在 Intel Mac 上通过 Xcode 26.6 本机编译和链接；本轮未改 XNU 源码，只重跑了本机 prelink。沿用四个 `cpu_number()` 导入槽映射，并新增 `ml_get_wake_timebase`、`ml_stack_remaining`、`vm_map_page_size`、`processor_info` 以及 IOPlatform quiesce/active action 的源级映射；另确认 IOService DriverKit `Stop_Invoke` 和 `Start_Invoke` 两个 wrapper。还把 TXM 缺失时 AppleImage4 的 storage hook 接到 pinned XNU 提供的非 TXM backend。pinned prelink 回归检查通过，owner-target 桩调用从 **20 降至 4**（4 个不同地址），`missing={}`、`mapping_complete=true`。本轮新增并验证 IOService `CreatePMAssertion_Invoke` 映射。当前候选 SHA-256 为 `a4dee7b487d9bd97e821e518c1312a0a89b0bb7804301ee402aa6503acd2f6ab`。仅 `com.apple.security.Image4` 的 4 个内部 helper 仍指向 `_unixnu_fileset_unmapped`：`0xfffffe000b2a1694`、`0xfffffe000b2a170c`、`0xfffffe000b2a1778`、`0xfffffe000b2a1798`。其代码行为不等同于已确认的 XNU 导出 API，尚未找到可安全替代的 pinned XNU 实现；因此没有把它们硬映射。候选仍是 `runtime_qualified=false`、`loadable=false`，不是可启动内核。
- 按设备仓库现有代码接入 NX729J 的 NativeUfs 与 NativeNovatekTouch；补入 Sheng 通用 HID 驱动。当前没有核实过的 NX729J 触控固件，因此构建时生成 0 长度固件标记，触控保持禁用，未把 Xiaomi Sheng 平板固件塞进手机镜像。source-driver 报告为编译通过、运行期未认证。
- GitHub Actions run [41583636227](https://github.com/Kofa1/UniXNU-nx729j/actions/runs/41583636227) 在 package 步骤失败；run [41585101552](https://github.com/Kofa1/UniXNU-nx729j/actions/runs/41585101552) 在 tools 步骤失败；run [41756531037](https://github.com/Kofa1/UniXNU-nx729j/actions/runs/41756531037) 的 tools 与 seed 成功、package 失败，镜像上传跳过。已确认步骤级状态，但连接不能读取日志正文，具体 package 错误尚未确认。Mac 本地 Xcode 构建是开发路径；仓库的慢速一设备打包 workflow 现改为仅手动触发，工具安装和人工打包仍可按需使用。不得据此宣称 CI 打包通过。
- 尚未生成 payload 或 boot image：本机 shell 没有安全的 `UNIXNU_UNIQUE_CHIP_ID` 环境变量；不会输出或复述 seed。未向手机发送内核，也未写任何分区。iOS 17 回退配置与产物保持原样。

下一步：继续从 pinned XNU 和原始 Image4 调用关系核实这 4 个 helper；只有确认等价实现后才添加映射并跑同一回归护栏。之后再移除 `--allow-missing`。之后才能把结果称为可加载候选；再用隐藏输入的设备 seed 打 payload/boot image，并通过 fastboot RAM 启动观察 DarwinBoot/XNU 入口。到达 GUI 仍需运行期 PMGR/平台、root、launchd、显示/Metal 与 PAC 工作；当前没有 iOS 27 真机启动或 PAC 资格证据。

## 2026-11-01 仓库与打包状态核对

- 设备分支 `codex/ios27-interactive-port` 当前 HEAD 为 `3cb4323b1ee69007d555cc30137890768f0c98c7`；UniXNU 与 UEFI 分别使用 `627c932a1573483dd44c29b48a113c3761dd8f55`、`20ac23d5e0937106c2129303dfc931b3390ae660`。
- GitHub Actions 最新记录仍是 [run 41285404011](https://github.com/Kofa1/UniXNU-nx729j/actions/runs/41285404011)，对应上述 HEAD，结果为失败；目前没有较新的分支运行。失败日志报告 `prelinked-corecrypto-oskext.patch:15` 格式错误。
- 已按 UniXNU 该提交中的 OS profile 核对 XNU `12377.121.6` / `ac9718fb1af618d5ce8678d0dc6e8a58f252216f`。先应用该提交 `patches/xnu-12377/native-security-init.patch`（它加入本设备补丁要移除的代码），再对设备补丁运行 `git apply --check`，当前补丁通过。对比上一设备提交中的补丁则会在第 15 行复现 `corrupt patch`。这说明当前提交包含了 hunk 格式修正，但与同一 HEAD 对应的 Actions 失败仍未解释；不能将该 CI 运行标记为通过。
- `scripts/package.sh --no-deps --check --os 27 --uefi ../uefi-sheng` 成功解析 71 个有序补丁并在构建前退出。该选项只检查配置与补丁清单，不等于应用整组补丁、编译或打包。
- Intel Mac：`x86_64`、macOS 26.7.1；Xcode 26.6（17F113）已选为开发者目录，iPhoneOS SDK 26.5 可用。Homebrew 未安装；MacPorts 2.12.7 已安装 `cmake`、`ninja`、`llvm-23`、`dtc`、`mtools`。另从 LLVM 23.1.4 构建了本地 `lld-link`。在 shell 中须把 `/opt/local/bin`、`/opt/local/libexec/llvm-23/bin` 与本地 LLD 的 bin 目录加入 `PATH`。
- 本机首次 XNU 构建发现设备归档 9 的两个输入问题：弱符号生成器重放整组 BSD/XNU 头文件而产生 IPC 声明冲突；带尾随注释的弱导入未被生成器识别。已在设备脚本中改为只生成所需的弱符号声明，并修正 `BootDiagExport.c` 的缺失符号导入。归档 9 现已编译通过。
- `native-stack-shift.patch` 已加入设备补丁清单，并对固定 XNU 源码运行 `git apply --check`。它提供 iPadOS 27 文件集绑定所需的栈对齐值，以及 prelink 重算所需的 32 字节 `__fips_hmacs` 字段。
- Intel Mac 上已完成 XNU 编译和链接，并生成本地 `kernel/kernel.macho`（95,813,632 字节，SHA-256 `b8a874c5f0b3de5c5f3eeb22966b252e780265e48f453ba68ae70c3d6ba2c71d`）。profile 指定的 RELEASE 文件集参考并未随干净工作区提供；按核心仓库 helper 改用本机 NX729J 树构建 RELEASE 参考时，链接因缺少设备归档符号而失败。随后使用同一构建的 DEVELOPMENT 内核作临时符号参考，成功生成实验性 prelink 候选。报告仍为 `runtime_qualified=false`、`loadable=false`，且将未解析函数导向报告桩；该文件尚未尝试手机启动或 PAC 验证。
- Intel Mac 已完成设备 package 构建；UEFI MemoryMapLib 补入缺失的 DTB carveout reservations，并拆分 ramoops 上方的 conventional-memory 区间后，NX729J 固件已重新编译成功。该改动已保存为设备仓库 patch，并在固定 UEFI commit 的干净 worktree 中验证可应用；当前 FD 为 3,145,728 字节，SHA-256 `eae7cefa0b876fc3594211c3d90b4e23737af5c503f752f7e8c039d07bf310e9`。它仍需真机验证；编译成功不代表设备已启动。
- 本地生成的 NX729J DTB 为 848,678 字节，SHA-256 `7541fab760d9f466d7565fc7ac0d3c30c52dec8c284ed9b72c12208b6f84376d`。预检保留固定 UEFI checkout 中原有、已跟踪且内容略有差异的 DTB；boot image 使用设备仓库生成的 DTB。
- 更新后的 NX729J 审计读取 iPadOS 27 OS profile 和 format-2 ADT。AOP message RAM 嵌在 AOSS MMIO aperture 内，二者使用同一 `NS_DEVICE` 属性；pinned PEI 校验会跳过 `PcdSystemMemoryBase` 以下的该类 register range，因此审计器按真实固件行为将此特定 alias 记为通过。审计现为 27 项、0 blocking；含新内存表的固件已编译，尚未验证新固件行为。
- iPadOS 27.0.1 (24A446) 的 StaticTrustCache 与 Cryptex1,SystemTrustCache 已从对应 IPSW 提取并组成 88,308 字节的本地 bundle，SHA-256 `dc655bcb2ddfaea214f9ec83659b3fc8d8b658bafac2b5a004fb4179a25c89bf`；该摘要已加入 iOS 27 `board.toml` 白名单。最初 payload 尝试因启用了 `native-ufs-root=1`、却没有该 iOS 27 内核可用的 PMGR 集成而被 core 正确拒绝。已将主线阶段调整为 kernel-entry bring-up，并暂时关闭 source storage/UFS root；待 iOS 27 PMGR ABI 审计完成后再启用。
- 后续 ADT 生成失败是因为 `/memory/reg` 有七段，不符合 pinned core“恰好一段连续 DRAM”的要求。已将 `dts/nx729j.dts` 的 ADT handoff 区间改为不与任何启用的 `/reserved-memory` 项重叠的 5 GiB 连续区域（base `0x8c0000000`、size `0x140000000`），同步 `payload.dram_size`；完整 16 GiB 物理布局仍保留在 `/ddr-regions`。同时补齐 `/cpus/timebase-frequency=19.2 MHz`、供 ADT 使用的根级 PSCI 声明，并禁用此转换器会误读为 CPU 的 Linux `cpu-map` 子树。pinned `devicetree.py` 已验证完整 ADT 生成路径。
- 已用用户提供的 seed 生成 payload；seed 仅传给本地构建进程，未写入报告或输出。payload 为 192 MiB，SHA-256 `0a4e9cab5d25fccc0e8c842a154b299fa8663a7d87d810d3d499d12c48cc03a6`，含 88,308 字节 iPadOS 27 trust cache、ADT 与 root-policy bundle。使用新 FD 重打包后的 boot image 为 203,812,864 字节，SHA-256 `456181a29f460dea59f93e48fbefe0a3bd9a7d89ddfa7645ba6947edb64040c3`；pinned packer 的解包往返校验通过，`boot.json` 标记 `hardware_tested=false`。这证明打包成功，不证明内核可加载或设备已启动。
- 已从 Google 官方渠道在本机安装 Platform Tools 37.0.1；Intel x86_64 Mac 的 fastboot 可运行，二进制目录作为本机工具加入忽略规则。当前 `fastboot devices` 返回 0 台设备，所以本轮没有向手机发送启动命令。设备连接并进入 bootloader 后，下一阶段可进行受控的 RAM 启动观察，不会写设备分区。
- pinned core 的 `scripts/audit-amfi-pmgr-contract.py` 因缺少预期的 `build/xnu-prelink/*-candidate.macho` 而退出 `No reference candidate available`。iPadOS 27 IPSW kernelcache 已在本地，但这个审计脚本依赖预生成候选；当前结果不是对 27.0.1 PMGR ABI 的验证。在取得正确参考输入并完成运行期验证前，PMGR/UFS root 仍关闭。
- 2026-10-22 的 UEFI 真机启动记录仍是旧证据，不代表 iPadOS 内核或用户空间已启动。
- iOS 17 回退配置与审计产物保留；本轮未改动它们。

下一步：用正确的 iPadOS 27.0.1 kernelcache/reference 输入完成 fileset 函数映射和 PMGR ABI 审计，再把可加载候选送到已连接的 NX729J 做受控 RAM 启动观察。当前 kernel/prelink 仍为 `runtime_qualified=false`、`loadable=false`；iOS 27 PMGR handoff 未实现，因此 boot image 只是集成产物，不是可启动系统。证明内核入口后，才能进入系统服务、UFS root、PAC 与 GUI bring-up。iOS 17 回退配置与产物保留。GitHub Actions run 41285404011 仍对应原提交且失败；本地改动未推送，也没有新的 Actions 运行。

一句话总结：**2026-10-22 的旧 UEFI 已在红魔 8 Pro+ 上走到 BDS；2026-11-01 的本地 iPadOS 27 集成 UEFI 已编译成功，但尚未上机验证。**旧真机记录中屏幕显示滚动日志，最后停在 Project Silicium Logo 和
`Failed to Find an Operating System`。这不是崩溃，是"没有操作系统可启动"的正常提示，
这是 2026-10-22 当时没有内核时的正常提示。现在本地已有 iPadOS 27 内核候选和完整 boot image，但候选仍标记 `loadable=false`；**阶段 B 正在进行，尚未证明内核入口。**

---

## 一、已完成

| 项目 | 产出 | 依据 |
|---|---|---|
| 机型身份 | `board.toml`：`nx729j` / SM8550-AB / msm-id `0x207` / DDR 16 GiB | 真机 DTB |
| **userdata 起始位置** | `first_lba = 0x296328`（2712360，4 KiB 扇区）**已确定，不用量** | 官方刷机包 `gpt_main0.bin` + `rawprogram0.xml` + `patch0.xml` 三处一致 |
| **ABL 性质** | 已确认是 EDK2 `QcomModulePkg`，不是老式 lk；LZMA 解开后 688 KB 可读内容 | `tools/fv_extract.py` 解包 `abl.img` |
| 目标系统 | 当前主线：iPadOS 27.0.1（24A446）；iOS 17.7.11（21H461）配置/审计内容作为回退保留 | `board.toml`、UniXNU OS profile |
| 内核配置 | `configs/nx729j_defconfig` | 照 sheng 的 SM8550 组合 |
| ADT 生成器 | `scripts/make-nx729j-adt.py` | 真机 DTB；二进制结构已回读校验 |
| 面板参数 | `docs/reference/panel/nx729j-panel.json`：三档时序 + 1349 字节初始化序列 | 真机 DTB，`--active` 追 phandle `0x6b2` |
| 预检 | `scripts/check-nx729j.py`：19 项 | 实跑通过 |
| 固件解包工具 | `tools/fv_extract.py`：UEFI FV → FFS → LZMA → 字符串 | 实跑，从 `abl.img` 解出 2121 条字符串 |
| 手机体检 | `tools/nx729j.py doctor` | 实跑通过（adb/fastboot 已自动找到） |
| 量分区 | `tools/nx729j.py measure --write board.toml` | 模拟设备端到端验证 |
| **fastboot 探测** | `tools/nx729j.py probe`：getvar 全量 + 解锁判定 + `fastboot boot` 阶梯测试 | **真机实跑通过（见下）** |
| **`fastboot boot` 放行** | `Sending 'boot.img' (98304 KB) OKAY` → `Booting OKAY` → `Finished` | **真机实测 2026-10-22，serial `b4b45a27`** |
| **userdata 末位** | `last_lba = 0x718bccd` 已写入 `board.toml`（原为 `0x0` 占位） | **真机 `partition-size:userdata` = `0x718BCD3000`** |
| 分区备份 | `tools/nx729j.py dump` | 逻辑验证 |
| 覆盖脚本 | `scripts/apply-to-sheng-fork.py` | 实跑验证 |
| **阶段 A 编译脚本** | `build/phase-a.sh` + `build/编译阶段A.bat` | 语法校验通过，**未在真实 Linux 上跑过** |
| 文档 | `GUIDE-从零开始.md`、`CHECKLIST-勾选清单.md`、`docs/reference/firmware-package-facts.md` | — |
| **UEFI 固件编译成功** | `SILICIUM_UEFI.fd`，**3145728 字节（= 0x300000，正好等于配置里声明的 FD size）** | WSL2 实跑，clang 20 核并行，约 2 分 20 秒 |
| **boot.img 打包成功** | `out/boot-nx729j.img`，**2437120 字节**，BootShim 192 字节 | `unixnu bootimg` 自带往返自校验全部通过 |
| **真机 boot 本轮结果** | `Sending 'boot.img' (2380 KB) OKAY` → `Booting OKAY` → `Finished. Total time: 10.353s` | 真机实测，serial `b4b45a27` |
| **boot 之后的状态** | adb 无设备、fastboot 无设备、**没有 9008 端口**（不是变砖），USB 完全没有枚举 | 现场排查，见第三节 |

### 这一轮编译踩掉的坑（都已修好，脚本可重跑）

1. **edk2 嵌套子模块是空的。** `Mu_Basecore` 是从 codeload 压缩包解开的，不是 `git submodule update`
   出来的，`.gitmodules` 里 9 个子模块目录全空。BaseTools 在 meta-data 阶段逐个校验
   `MdePkg.dec` / `MdeModulePkg.dec` 的 `[Includes]`，遇到空目录就 `error 000E` 直接退出。
   真正需要的是 4 个：`mipisyst`、`libfdt`、`brotli`（两处）、`libspdm`。
   已用 `build/seed-edk2-modules.sh` 从本地缓存里按**锁定 commit**灌进去。
2. **`VfrCompile` 二进制没生成。** BaseTools 的 C 工具是在装 `g++` 之前编的，C++ 那几个被跳过。
   后果是 `DtPlatformDxe` 的 `DtPlatformHii.vfr` 没被编译成 `.c`，
   报 `clang: error: no such file or directory: .../DtPlatformHii.c`。
   `cd BaseTools/Source/C && make -j20` 补出来后，13 个工具齐全。
3. **内存映射的区域名超长。** 从 DTB 生成的条目直接用节点名
   （`trust_ui_vm_vblk0_ring@0xf78f8000`，33 字符），而结构体 `Name[]` 只有 32 字节，
   clang 在 `-Werror` 下报 `initializer-string for char array is too long`。
   已去掉 `@地址` 后缀（地址本来就有单独字段），`tools/fix-memmap-names.py` 可复查。
4. **`header_version = 4` 与打包自校验冲突。** pinned `uefi-sheng` 的 `nx729j.toml` 原先写的是 4，
   但 `unixnu` 的 `verify()` 是按 v0/v1/v2 头部布局解析的（偏移 36 读 pagesize、40 读 header_version），
   v4 头部没有这两个字段，必然报 `boot image header does not match the requested parameters`。
   设备仓库现以 `[bootimg.image].header_version = 0` 覆盖该值，打包往返校验通过。
5. **设备 DTB 未自动传给独立 bootimg 命令。** 当前需先运行 `scripts/build-nx729j-dtb.py`，
   再用 `--dtb build/nx729j/nx729j.dtb` 显式指定生成的 DTB。

### 这一轮从你的刷机包里新挖到的东西

1. **`lba_bytes` 必须是 4096，不是 512。** 这个包所有分区都写 `SECTOR_SIZE_IN_BYTES="4096"`。
   按 512 算会让 `first_lba` 的含义整体错 8 倍。不过已核实：这个几何在 UniXNU 里
   **只用于"镜像装不装得下"的容量校验**，不参与写入，所以填错是精度问题、不是变砖问题。
2. **userdata 下面紧挨着 256 MiB 的 `rawdump`**，`userdata` 的起点 = `rawdump` 末格 +1，
   这个数是 GPT 表项里直接读出来的。
3. **ABL 编译路径里写的是 NX729S（8S Pro）**，不是 NX729J。努比亚很可能让 8 Pro/8S Pro
   共用同一份 ABL，所以 `getvar product` 有可能回 `NX729S`——那不是手机有问题。
4. **ABL 会改写 DTB 的 splash 和 demura 节点**（`Splash memory region after updating:`、
   `/reserved-memory/demura_region_1`）。`nx729j.dtb` 里已有 `cont_splash_region`，所以暂时不是问题。
5. **阶段 A 完全不需要面板参数**：`nx729j.dsc` 里 `USE_CUSTOM_DISPLAY_DRIVER = 0`，
   直接用 bootloader 点亮的 1116×2480×32bpp 帧缓冲。DSI、DSC、初始化序列统统不用碰。

---

## 二、历史 Windows/WSL 环境记录（已归档）

以下内容记录 2026-10-22 的阶段 A Windows/WSL 环境，不是当前构建步骤。当前 iPadOS 27 主线已在 Intel Mac 上使用 Xcode 26.6 与 iPhoneOS SDK 26.5 完成内核、打包和固件构建；当前状态以本文件顶部的 2026-11-01 记录为准。无需按下方 WSL 重启说明操作。

| 需要什么 | 现在状态 | 谁能解决 |
|---|---|---|
| adb / fastboot | ✅ 已装到 `tools/platform-tools/`（adb 1.0.41 / fastboot 37.0.1） | — |
| Python | ✅ 3.13 可用 | — |
| `wsl.exe` 调用 | ✅ **已解除黑名单**，现在能正常调用 | 你已处理 |
| WSL 功能 | ✅ `Microsoft-Windows-Subsystem-Linux` + `VirtualMachinePlatform` **已启用** | 我做了，**等重启** |
| Ubuntu rootfs | ✅ 已预下载 `work/wsl/ubuntu-base-24.04.4-base-amd64.tar.gz` | 我做了，重启后免下载直接导入 |
| 硬件虚拟化 | ✅ `VirtualizationFirmwareEnabled = True` | 本来就有 |
| macOS（编内核、做系统镜像） | ⚠️ Intel Mac 可用，但当前未选中完整 Xcode，iPhoneOS SDK 不可用 | 2026-11-01 本机检查；选择/安装 Xcode 26 或更早版本后再开始内核编译 |

### 重启之后，只有一步

```powershell
powershell -ExecutionPolicy Bypass -File "D:\刷机\IOS\build\安装WSL并编译.ps1"
```

这个脚本会自己做完：确认 WSL2 内核 → 导入 Ubuntu（用预下载的 rootfs，不走应用商店）→
换清华 apt 源 → 调 `build/phase-a.sh` 编译 → 把 `boot-nx729j.img` 拷到 `out\`。

想手工来也行，只要记住 Ubuntu 是**导入**的而不是商店装的：

```powershell
wsl --set-default-version 2
wsl --import Ubuntu "D:\刷机\IOS\work\wsl\Ubuntu" "D:\刷机\IOS\work\wsl\ubuntu-base-24.04.4-base-amd64.tar.gz" --version 2
wsl -d Ubuntu -u root -- bash "/mnt/d/刷机/IOS/build/phase-a.sh"
```

> 为什么不用 `wsl --install -d Ubuntu`：那条路要连 Microsoft Store，本机到 store 的
> 网络时好时坏；而 `cdimage.ubuntu.com` 实测可达，导入这条路更稳。

---

## 三、真机实测结果（2026-10-22，已连机完成）

### A. 我们自己编的固件：完整启动到 BDS（本轮里程碑）

把 `out/boot-nx729j.img`（我们自己编的 UEFI，不是刷机包里的）送进去：

```
Sending 'boot.img' (2380 KB)                       OKAY [  0.075s]
Booting                                            OKAY [ 10.117s]
Finished. Total time: 10.195s
```

**ABL 接受了镜像并跳转了**——说明 BootShim 的 ARM64 头、FD 基址 `0xA7100000`、
DTB 附加方式都是对的，否则 ABL 会在 `Booting` 之前就拒绝。

#### 日志是怎么拿到的

设备没有 UART，唯一的观测通道就是屏幕本身。用手机录屏 + `ffmpeg` 抽帧还原：

```
adb pull /sdcard/DCIM/Camera/video_20261022_145758.mp4
ffmpeg -i run-1457.mp4 -vf "fps=1,scale=1200:-1" frames/f_%02d.jpg    # 22 帧
```

录像 4K / 60fps / 22.5 秒，覆盖了 boot 之后的前 22 秒。

#### 实际看到的启动序列

| 时刻 | 画面 | 阶段 |
|---|---|---|
| 14:57:58 | REDMAGIC Logo + Powered by Android | ABL 开机图 |
| 14:58:00 | 黑屏一闪 | 切到 UEFI 帧缓冲 |
| 14:58:03 | 满屏白色滚动日志 `Loading driver at 0x... EntryPoint=0x...` | DXE 派发驱动 |
| 14:58:09 | 日志停在顶部，中央出现 **Project Silicium** 大 Logo | BDS 进入 |
| 14:58:09 ~ 14:58:16 | 画面静止 | BDS 枚举启动项 |
| 14:58:17 | 感叹三角 + `Failed to Find an Operating System` | 无 OS → 复位 |

#### 从日志确定的事实

**1. 显示通路完全正常。**

`USE_CUSTOM_DISPLAY_DRIVER = 0`（直接复用固件自己初始化的帧缓冲）这条路走通了。
不需要写 DSI 面板初始化、不需要碰 DSC 压缩、不需要提取时序参数。
待办里"显示绑定"那一项可以直接划掉。

**2. DXE 驱动基本全部加载成功。**

日志里有大段连续的 `Loading driver at 0x... EntryPoint=0x...`，覆盖
`HardwareTimer` / `RealTimeClock` / `SecurityStubDxe` / `PrintDxe` 等；
`Installed Fat filesystem on BE0F1A18` 说明块设备栈也起来了。

**3. QCOM 安全世界调用失败，但全部良性。**

```
_diag_get_config_info(): Target 0x7F not supported
_scm_call failed, TxStatus = 0xFFFFFEF7
_diag_get_debug_policy(): System call failed
Failed to start <xxx> Enabler, a TA, status = 1
PIL-SPSS Failed to get MDT size
```

这些是 SCM / PIL / TrustZone 相关调用。**设备 `secure=yes` 且
`critical unlocked=false`，未签名的 TZ 镜像本来就加载不了**，所以失败是预期内的；
而且它们都没有阻断启动——UEFI 照样走到了 BDS。

**4. 两条真实缺口。**

```
Detecting USB Storage
... no USB devices found on first attempt
```

- **没有输入设备**：USB 控制器起来了但没枚举到键盘；触控（Goodix GT9916）
  驱动还没写，所以屏幕点不了。
- **NVRAM 未持久化**：`... Dxe at 0x0008555000 start failed: Not Found`。
  影响是启动项存不下来，每次都要重新枚举。

**5. 最后的三角不是崩溃。**

`Failed to Find an Operating System` 是 edk2 BDS 在没有任何可启动项时的标准提示，
随后 `ResetSystem()` 复位（所以 14:58:44 回到关机充电）。换句话说：

> UEFI 走完了它该走的全部流程，只是手上没有 iOS 内核可以交棒。

#### 阶段 A 判定

| 项目 | 结论 |
|---|---|
| BootShim 头 / FD 基址 / DTB 附加 | 通过，ABL 放行 |
| SEC / PEI / DXE 初始化 | 完成 |
| 帧缓冲显示 | 正常，日志与 Logo 都能画 |
| BDS 启动管理 | 正常，无启动项时报错语义正确 |
| USB 输入 | 缺（无键盘、无触控驱动） |
| NVRAM | 未持久化 |
| OS 内核 | 阶段 B，需 macOS |

**阶段 A 完成。** 剩下两项（USB 输入、NVRAM）不影响"能不能启动 iOS"这个主目标，
属于可用性改进，可以放到阶段 C 之后再做。

---

设备 `b4b45a27`，RedMagicOS 10.0.12（Android 15）。实测拿到的东西：

| 变量 | 实测值 | 意义 |
|---|---|---|
| `unlocked` | **yes** | bootloader 已解锁，可以刷 |
| `secure` | yes | 仍会验签，所以**不能**随便刷引导链分区 |
| `product` | **kalama** | 平台代号，**不是**原先猜的 `NX729S`，ABL 没上报机型名 |
| `current-slot` | a | 当前在 A 槽 |
| `partition-size:userdata` | `0x718BCD3000` = 454.2 GiB | 推出 `last_lba = 0x718bccd` |
| **`Device critical unlocked`** | **false** | **critical 分区未解锁**，`xbl`/`abl` 这类不能动 |
| `fastboot boot` | **OKAY** | **总闸门通过** |

`fastboot boot` 的完整输出（这是最重要的一行）：

```
Sending 'boot.img' (98304 KB)                      OKAY [  3.020s]
Booting                                            OKAY [ 10.160s]
Finished. Total time: 13.228s
```

跑完之后手机自己回到了 Android，`adb devices` 正常，**没有写任何分区**。

### 注意 `critical unlocked: false`

这个不影响阶段 A，因为 `fastboot boot` 只往内存里放镜像、不落盘。
但它意味着**以后不能直接刷 `xbl` / `abl` / `tz` 等关键分区**，一旦刷坏就是高通 9008 救砖。
所以后续任何需要"写引导链"的方案都要先绕开这一点，优先走 `fastboot boot` 的路线。

---

## 四、待做，需要真正写代码

| 项目 | 现状 | 缺什么 | 难度 |
|---|---|---|---|
| 编内核 | **唯一卡点** | **必须 macOS**（`xcodebuild` + iphoneos SDK + `compression_tool`） | 4-8 小时机器时间 |
| 系统镜像 | 未开始 | **必须 macOS**（`hdiutil`） | 1-2 小时 |
| Goodix GT9916 触控 | 只有规格 | 协议层 + 报告解析层。Goodix 是**芯片算坐标**，和小米平板的 Novatek（软件算质心）完全不同，不能照抄。**不阻塞 iOS 启动**，只影响 UEFI 菜单能不能点 | 中高 |
| NVRAM 持久化 | 报 `start failed: Not Found` | 找一个能落盘的变量存储后端（UFS 分区或文件） | 中 |
| ~~显示绑定~~ | **已完成** | 帧缓冲直接可用，`USE_CUSTOM_DISPLAY_DRIVER = 0` 走通 | — |

---

## 五、我不会做的事

- 不编造 `last_lba`。现在已经从真机读到了确切值，这条不再有争议；顺带纠正早先的说法：
  这个几何在 UniXNU 里**只参与"镜像装不装得下"的容量校验**，不参与写入，
  所以算错是精度问题，不是变砖问题。
- 不假装编译成功。`phase-a.sh` 写好了但**没有在真实 Linux 上跑过**，跑完之前它都算"未验证"，
  而不是"已经能用了"。
- 不越过 `critical unlocked: false` 去刷引导链分区。任何需要写 `xbl`/`abl`/`tz` 的方案，
  在拿到 9008 救砖能力之前都不做。
- 不说"再等一会儿就好了"。`fastboot boot` 这次是明确放行（`Booting OKAY`），
  如果后面编出来的固件被拒，那就是被拒，我会直接说。
