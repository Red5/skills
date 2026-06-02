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
    echo "Error: python3 is required to query Docker Hub API responses." >&2
    exit 1
  fi
}

resolve_latest_release_tag() {
  python3 - "$IMAGE_REPO" <<'PY'
import json
import sys
import urllib.error
import urllib.parse
import urllib.request

image_repo = sys.argv[1]
base_url = f"https://hub.docker.com/v2/repositories/{image_repo}/tags"
params = {"page_size": 100, "ordering": "last_updated"}
url = f"{base_url}?{urllib.parse.urlencode(params)}"

all_tags = []

def last_updated(item):
    return item.get("last_updated") or ""

while url:
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.URLError as exc:
        print(f"Error: failed to fetch tags from Docker Hub ({url}): {exc}", file=sys.stderr)
        sys.exit(1)

    all_tags.extend(payload.get("results", []))
    url = payload.get("next")

for tag in sorted(all_tags, key=last_updated, reverse=True):
    name = tag.get("name", "")
    # Skip `latest` because it is an alias and not a concrete release version.
    if name and name != "latest":
        print(name)
        break
else:
    # Fallback when only `latest` exists, or no tags are returned.
    print("latest")
PY
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
