# Docker

The image serves the API and the built frontend from a single port, `8501`.

Published on Docker Hub as
[`legroom2669/my-clippings-parser`](https://hub.docker.com/r/legroom2669/my-clippings-parser),
built for `linux/amd64` and `linux/arm64`.

| Tag | Meaning |
| --- | --- |
| `1.0.0` | Pinned release. Use this when you want the deployment to stay put. |
| `latest` | Whatever the most recent release is. |

## Running

```powershell
docker run --rm -p 8501:8501 -v "${PWD}\data:/data" legroom2669/my-clippings-parser:1.0.0
```

```bash
docker run --rm -p 8501:8501 -v "$PWD/data:/data" legroom2669/my-clippings-parser:1.0.0
```

Open `http://127.0.0.1:8501`. The `/data` volume holds everything the app keeps
between runs — see [Local History](README.md#local-history). Point `HISTORY_DIR`
somewhere else if you prefer a different path inside the container.

The image has a `HEALTHCHECK` on `/api/health`, so `docker ps` and Compose
restart policies can tell a wedged backend from a live one.

## Building locally

```bash
docker build -t legroom2669/my-clippings-parser:dev .
```

The build is two-stage: `node:22-slim` runs `npm ci && npm run build` in
`frontend/`, and `python:3.11-slim` installs the backend and copies
`frontend/dist` in. That `dist` is why the runtime serves both from one port —
`api.py` mounts it at `/` when the directory exists.

To reproduce a published multi-arch build:

```bash
docker buildx build --platform linux/amd64,linux/arm64 \
  -t legroom2669/my-clippings-parser:1.0.0 \
  -t legroom2669/my-clippings-parser:latest \
  --push .
```

## Running as a non-root user

By default the container runs as root. Two ways to change that, and they can
both be left alone if you don't care:

**`PUID` / `PGID`** — the container starts as root, takes ownership of
`HISTORY_DIR`, and drops to that user before starting the app. This is the
convenient option on a NAS: no need to prepare ownership on the host.

```yaml
services:
  parser:
    image: legroom2669/my-clippings-parser:1.0.0
    environment:
      - TZ=America/Sao_Paulo
      - HISTORY_DIR=/data/history
      - PUID=2001
      - PGID=2001
    ports:
      - '8501:8501'
    restart: unless-stopped
    volumes:
      - /mnt/tank/apps/parser/history:/data/history
```

Setting only one of them defaults the other to `1000`. Leaving both blank keeps
the historical behavior — the app runs as root.

**Docker's own `user:`** — if you set `user:` (or `--user`), the container never
runs as root at all, which is the stricter posture. The entrypoint notices it is
already unprivileged and starts the app directly, so `PUID`/`PGID` are ignored
and the host directory has to be writable by that UID beforehand:

```sh
chown -R 2001:2001 /mnt/tank/apps/parser/history
```

Both work with `security_opt: [no-new-privileges:true]`.

## Environment variables

| Variable | Default | Effect |
| --- | --- | --- |
| `HISTORY_DIR` | `/data` | Where the history store and `analyses/` live. |
| `PUID` / `PGID` | unset | Drop to this UID/GID after chowning `HISTORY_DIR`. |
| `TZ` | UTC | Container timezone. Display formatting is `America/Sao_Paulo` regardless. |

## `docker-entrypoint.sh`

Runs before the app and has three paths, all of which have to keep working:

1. Started already non-root (`--user` / `user:`) — execs straight through.
2. Root with `PUID`/`PGID` blank — creates `HISTORY_DIR` and runs as root.
3. Root with either set — creates and chowns `HISTORY_DIR`, then drops
   privileges via `gosu`.

The `chown` failure is swallowed on purpose: on a read-only volume or with user
namespace remapping it cannot succeed, but the app may still have write access.

`/data` is created with the sticky bit (`chmod 1777`) in the Dockerfile —
without it, `--user` with no volume mounted cannot write to the root-owned
`/data` and the first upload fails with a 500.
