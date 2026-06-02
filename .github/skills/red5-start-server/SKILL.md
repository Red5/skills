---
name: red5-start-server
description: Resolve the latest Red5 Docker release tag, pull the image, and start a running Red5 server container. Use this when asked to start Red5 from Docker or run the newest Red5 server container.
---

# red5-start-server

Start a Red5 server container from the latest Docker Hub release.

## Prerequisites

- Docker must be installed and running.
- Python 3 must be available in PATH.
- The current user must be able to run Docker commands.

## Workflow

1. Resolve the newest release tag from Docker Hub for `red5pro/server`.
2. Pull the image for that resolved tag.
3. Replace any existing `red5-server` container.
4. Start a detached container with default Red5 ports exposed.
5. Report the chosen image tag and running container status.

Run:

```bash
bash .github/skills/red5-start-server/scripts/start-red5-server.sh
```

## Optional environment overrides

- `IMAGE_REPO` (default `red5pro/server`)
- `CONTAINER_NAME` (default `red5-server`)
- `HOST_HTTP_PORT` (default `5080`)
- `HOST_RTMP_PORT` (default `1935`)

Example:

```bash
IMAGE_REPO=red5pro/server CONTAINER_NAME=my-red5 HOST_HTTP_PORT=15080 HOST_RTMP_PORT=11935 \
  bash .github/skills/red5-start-server/scripts/start-red5-server.sh
```
