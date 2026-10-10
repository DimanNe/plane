#!/bin/sh
# Builds every image from this checkout and restarts one local instance on them: the way to try a change to the
# API, which a copied web build cannot show.
#
# The image names are the same for every instance on the machine: an instance that is started later, by anybody,
# runs the images that were built last, and applies their migrations to its data. So the build and the restart
# are one step under a lock, and this is not for a machine where an instance with data that matters may be
# started meanwhile.
# usage: claude/tools/rebuild_and_restart.sh <run-dir> <port>
set -eu
RUN_DIR=$(realpath "$1")
PORT="$2"
cd "$(dirname "$0")/../.."
exec 9> /tmp/plane-local-images.lock
flock 9
python3 scripts/plane_runtime.py prepare
python3 scripts/plane_runtime.py stop --run-dir "$RUN_DIR"
python3 scripts/plane_runtime.py start --run-dir "$RUN_DIR" --port "$PORT"
