# Portability and recovery

The Git-tracked core is intentionally separated from private/cached binaries.

## Fresh-machine recovery

```bash
git clone https://github.com/originova05-arch/ContinueRetro-PS1.git ContinueRetro-PS1
cd ContinueRetro-PS1
./scripts/bootstrap.sh
./scripts/doctor.sh
```

`bootstrap.sh` first uses `tools/cache/`, then exact locked download/source refs. It never assumes `/usr/local` or `/tmp` contains a required project tool. Third-party versions and hashes are pinned in `tools/locks/`.

## Private assets

Retail game images and BIOS dumps belong in `PRIVATE/` and are excluded from Git. Their expected hashes are tracked, but the bytes are not. Keep a separate personal/offline backup of `PRIVATE/` if you want a truly offline migration.

The current Zoids 2 private asset targets are:

- base BIN SHA-256 `4f41fd9dc2e7f2ae2b336f9b79f7ac0311a50a651579a588923ba3976c982ceb`
- base CUE SHA-256 `2ff6ee3373db49bd53ebee58720548153f99fa6d6e15762ad73caacdec470546`
- SCPH5500 BIOS SHA-256 `9c0421858e217805f4abe18698afea8d5aa36ff0727eb8484944e00eb5e7eadb`

## Offline tool cache

`tools/cache/` is Git-ignored because it can contain large third-party archives/AppImages. On machines where network access is unreliable, preserve that directory in a private backup. `bootstrap.sh` verifies locked SHA-256 values before use.

## Rebuild source

Exact source refs are stored in `tools/locks/toolchain.lock.tsv`. On a networked host run:

```bash
CR_FETCH_SOURCES=1 ./scripts/bootstrap.sh
```

This populates optional `tools/src/<third-party>/` clones at exact locked refs. Project-owned utilities and build scripts are tracked directly and do not require a download.
