# GitHub persistence

Canonical repository: `https://github.com/originova05-arch/ContinueRetro-PS1.git`.

The repository stores the portable project core: scripts, project-owned source, configs, documentation, checkpoints, hashes, tool lock metadata, and per-game reproducible workflows.

Do not put `PRIVATE/`, BIOS, original disc images, rebuilt full images, or normal `tools/cache` / `tools/installed` caches into the public Git repository. The normal repository is designed to reconstruct tools using `bootstrap.sh` and the lockfile. Large third-party binaries can be kept in private storage/Git LFS/releases if explicitly desired later.
