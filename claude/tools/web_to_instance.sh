#!/bin/sh
# Builds the web app of this checkout and copies it into the proxy of a running local instance, so that a change
# to the web app is seen in a browser about a minute later, without building an image or restarting anything.
# A change to the API needs rebuild_and_restart.sh instead.
# usage: claude/tools/web_to_instance.sh <run-dir>
set -eu
RUN_DIR=$(realpath "$1")
cd "$(dirname "$0")/../.."
# The web app is built with the values the image is built with.
VITE_VALUES=$(sed -n 's/^ENV \(VITE_.*\)$/\1/p' scripts/runtime/clients.Dockerfile)
[ -n "$VITE_VALUES" ] || { echo "No 'ENV VITE_...' line in scripts/runtime/clients.Dockerfile" >&2; exit 1; }
eval "export $VITE_VALUES"
pnpm turbo run build --filter=web
PROXY=$(docker ps --filter "label=org.plane.local.target=$RUN_DIR" --filter "label=org.plane.local.service=proxy" --format '{{.Names}}')
[ -n "$PROXY" ] || { echo "No running proxy of an instance in $RUN_DIR" >&2; exit 1; }
docker cp apps/web/build/client/. "$PROXY:/srv/web/"
echo "The web build of $(pwd) is in the instance of $RUN_DIR"
