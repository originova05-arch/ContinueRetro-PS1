# Zoids 2 — Thai localization

- Disc ID: `SLPS_033.89`
- Volume ID: `SLPS_03389`
- Region: Japan / NTSC-J
- Disc: one `MODE2/2352` raw data track
- Canonical base: `BASE_SHA256.txt`

## Translation policy

Translate Japanese into **natural, context-appropriate Thai**, not stiff word-for-word Thai. Short English UI/proper names may remain where appropriate; long English passages that players should understand are translated into Thai.

## Reproducible workflow

```bash
./extract.sh
./patch.sh
./build.sh
./verify.sh
```

## Current technical milestone

Shift-JIS/CP932 text is directly visible in `TITLE.BIN` and the main story data `ZOIDS_PS.DAT`. Runtime QA through DuckStation works. Before bulk translation, the Thai font/renderer must pass a multi-word runtime sample with:

- font cell **16×13**
- visible inter-glyph spacing **2 px**
- upper/lower marks **1 px** from the base glyph
- optical spacing for leading vowel `เ` corrected to the same effective 2 px as other glyphs

The old one-off proof temporarily changed `ゲーム開始` to `ทดสอบ` and was reported to touch LBAs `458`, `460`, `47997`. Since its ad-hoc generator and output image were not retained, it is historical evidence only, not a release parent or reproducible patch.

## Baseline rebuild proof

On 2026-09-02, `dumpsxiso 2.30` → `mkpsxiso 2.30` rebuilt the unmodified extracted disc to a BIN that is **byte-identical** to the canonical base:

`4f41fd9dc2e7f2ae2b336f9b79f7ac0311a50a651579a588923ba3976c982ceb`

The generated CUE differs only in the referenced BIN filename (`ZOIDS2_THAI_BUILD.bin`). This establishes a safe reproducible round-trip baseline before translation patches are applied.
