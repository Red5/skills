#!/usr/bin/env bash
set -euo pipefail

IMAGE_REPO="${IMAGE_REPO:-red5pro/server}"
CONTAINER_NAME="${CONTAINER_NAME:-red5-server}"
HOST_HTTP_PORT="${HOST_HTTP_PORT:-5080}"
HOST_RTMP_PORT="${HOST_RTMP_PORT:-1935}"

resolve_latest_release_tag() {
  local api_url="https://hub.docker.com/v2/repositories/${IMAGE_REPO}/tags?page_size=100&ordering=last_updated"

  curl -fsSL "$api_url" | python -c '
import json
import sys

payload = json.load(sys.stdin)
for tag in payload.get("results", []):
    name = tag.get("name", "")
    if name and name != "latest":
        print(name)
        break
else:
    print("latest")
'
}

LATEST_TAG="$(resolve_latest_release_tag)"
IMAGE_REF="${IMAGE_REPO}:${LATEST_TAG}"

echo "Resolved latest release: ${IMAGE_REF}"
echo "Pulling image..."
docker pull "$IMAGE_REF"

if docker ps -a --format '{{.Names}}' | grep -Fxq "$CONTAINER_NAME"; then
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
