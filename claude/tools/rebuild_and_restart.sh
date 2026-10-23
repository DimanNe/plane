#!/bin/sh
# Builds every image from this checkout and restarts one local instance on them: the way to try a change to the
# API, which a copied web build cannot show.
#
# Every instance started with the same image prefix runs the images that were built last under it, and applies
# their migrations to its data. So the build and the restart are one step under a lock of that prefix.
# usage: claude/tools/rebuild_and_restart.sh <run-dir> <bind> <image-prefix>, such as 127.0.0.1:18580 plane-47
set -eu
RUN_DIR=$(realpath "$1")
BIND="$2"
IMAGE_PREFIX="$3"
cd "$(dirname "$0")/../.."
exec 9> "/tmp/plane-local-images-$IMAGE_PREFIX.lock"
flock 9
python3 scripts/plane_runtime.py prepare --image-prefix "$IMAGE_PREFIX"
python3 scripts/plane_runtime.py stop --run-dir "$RUN_DIR"
python3 scripts/plane_runtime.py start --run-dir "$RUN_DIR" --bind "$BIND" --image-prefix "$IMAGE_PREFIX"
