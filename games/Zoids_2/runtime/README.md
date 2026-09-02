# Runtime QA procedure

Reference runtime: DuckStation `0.1-11826-gfe2306b1f`, Japanese BIOS `SCPH5500.BIN`.

In the container/Xvfb environment use the software renderer. If the game does not respond to D-pad/Start navigation, open the DuckStation quick menu and choose **Toggle Analog**; this was runtime-confirmed for Zoids 2.

For every retained test milestone save: screenshot(s), tested build SHA-256, parent/base SHA-256, changed-sector list/allowlist, emulator version/config, result (PASS/FAIL), and rollback target.
