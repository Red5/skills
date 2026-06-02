#!/usr/bin/env bash
set -euo pipefail

IMAGE_REPO="${IMAGE_REPO:-red5pro/server}"
CONTAINER_NAME="${CONTAINER_NAME:-red5-server}"
HOST_HTTP_PORT="${HOST_HTTP_PORT:-5080}"
HOST_RTMP_PORT="${HOST_RTMP_PORT:-1935}"

require_tools() {
  if ! command -v docker >/dev/null 2>&1; then
    echo "Error: docker is required but not found in PATH." >&2
    exit 1
  fi

  if ! command -v python3 >/dev/null 2>&1; then
    echo "Error: python3 is required to parse Docker Hub API responses." >&2
    exit 1
  fi
}

resolve_latest_release_tag() {
  local api_url="https://hub.docker.com/v2/repositories/${IMAGE_REPO}/tags?page_size=100&ordering=last_updated"
  local payload

  if ! payload="$(curl -fsSL "$api_url")"; then
    echo "Error: failed to fetch tags from Docker Hub (${api_url})." >&2
    exit 1
  fi

  printf '%s' "$payload" | python3 -c '
import json
import sys

payload = json.load(sys.stdin)

def last_updated(item):
    return item.get("last_updated") or ""

tags = sorted(payload.get("results", []), key=last_updated, reverse=True)
for tag in tags:
    name = tag.get("name", "")
    if name and name != "latest":
        print(name)
        break
else:
    print("latest")
'
}

require_tools
LATEST_TAG="$(resolve_latest_release_tag)"
IMAGE_REF="${IMAGE_REPO}:${LATEST_TAG}"

echo "Resolved latest release: ${IMAGE_REF}"
echo "Pulling image..."
docker pull "$IMAGE_REF"

if docker inspect "$CONTAINER_NAME" >/dev/null 2>&1; then
  echo "Removing existing container: ${CONTAINER_NAME}"
  docker rm -f "$CONTAINER_NAME" >/dev/null
fi

echo "Starting container: ${CONTAINER_NAME}"
docker run -d \
  --name "$CONTAINER_NAME" \
  -p "${HOST_HTTP_PORT}:5080" \
  -p "${HOST_RTMP_PORT}:1935" \
  "$IMAGE_REF" >/dev/null

echo "Container started successfully."
docker ps --filter "name=^${CONTAINER_NAME}$" --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}'
