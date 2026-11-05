# NX729J iPadOS 27 corecrypto startup

ENTRY-03 reached native XNU on the phone, completed both platform initialization calls (ENTRY-STAGE=3), and panicked at prng_random.c:335 (!prng_ready). This assertion reports a second registration of an already initialized PRNG.

The iPadOS 27 configuration uses XNU_CRYPTO_BOOTSTRAP=source, matching the Sheng source-bootstrap path. Shared native-security-init.patch preserves source_corecrypto14_start_once in OSKext; the legacy NX729J prelinked-corecrypto-oskext.patch removed that guard. The new board selection uses patches/xnu/series-source and leaves the shared guard intact. The legacy series is retained for configurations that omit the source bootstrap. No random data, crypto callbacks, or successful selftest results are fabricated.

The firmware from ENTRY-03 is reused. ENTRY-04 remains a single-CPU diagnostic with no root filesystem or Data seed; a later root-device stop is expected. It does not enable GUI or GPU startup. iOS 17 artifacts are unchanged.
