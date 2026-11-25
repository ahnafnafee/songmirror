#!/bin/sh
set -eu

: "${SONGMIRROR_AUTH_USERNAME:?Set an owner username in Render}"
: "${SONGMIRROR_AUTH_PASSWORD:?Set an owner password in Render}"

# Mounts can arrive owned by root. Fix the mount and leave the app unprivileged.
mkdir -p /data/downloads
chown 1000:1000 /data /data/downloads

if [ -z "${SONGMIRROR_PUBLIC_URL:-}" ] && [ -n "${RENDER_EXTERNAL_URL:-}" ]; then
  export SONGMIRROR_PUBLIC_URL="$RENDER_EXTERNAL_URL"
fi

exec setpriv --reuid=1000 --regid=1000 --clear-groups "$@"
