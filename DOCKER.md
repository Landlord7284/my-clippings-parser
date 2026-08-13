# Docker

The image serves the API and the built frontend from a single port, `8501`,
for `linux/amd64` and `linux/arm64`.

```bash
docker pull ghcr.io/landlord7284/my-clippings-parser:1.0.1
```

Also on Docker Hub as `legroom2669/my-clippings-parser`, same image. Use `1.0.1`
to pin a release, or `latest` to follow the newest one.

## Running

```bash
docker run --rm -p 8501:8501 -v "$PWD/data:/data" ghcr.io/landlord7284/my-clippings-parser:1.0.1
```

```powershell
docker run --rm -p 8501:8501 -v "${PWD}\data:/data" ghcr.io/landlord7284/my-clippings-parser:1.0.1
```

Open `http://127.0.0.1:8501`. The `/data` volume holds everything the app keeps
between runs — see [Local History](README.md#local-history). Set `HISTORY_DIR`
to use a different path inside the container.

The image has a `HEALTHCHECK` on `/api/health`, so `docker ps` and Compose
restart policies can tell a wedged backend from a live one.

## Compose

```yaml
services:
  parser:
    image: ghcr.io/landlord7284/my-clippings-parser:1.0.1
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

## Environment variables

| Variable | Default | Effect |
| --- | --- | --- |
| `HISTORY_DIR` | `/data` | Where the history store and `analyses/` live. |
| `PUID` / `PGID` | unset | Run as this UID/GID instead of root. |
| `TZ` | UTC | Container timezone. Dates are displayed as `America/Sao_Paulo` regardless. |

## Running as a non-root user

By default the container runs as root. Two ways to change that:

**`PUID` / `PGID`** — the container takes ownership of `HISTORY_DIR` and drops
to that user before starting the app, so the host directory needs no
preparation. Setting only one defaults the other to `1000`.

**Docker's own `user:`** — with `user:` (or `--user`) the container never runs
as root at all. `PUID`/`PGID` are then ignored, and the host directory has to be
writable by that UID beforehand:

```sh
chown -R 2001:2001 /mnt/tank/apps/parser/history
```

Both work with `security_opt: [no-new-privileges:true]`. On a read-only volume
the ownership fix is skipped silently — the app still starts if it can write.

## Building it yourself

```bash
docker build -t my-clippings-parser:dev .
```

Two stages: `node:22-slim` builds the frontend, `python:3.11-slim` installs the
backend and copies `frontend/dist` in. That `dist` is why one port serves both.
