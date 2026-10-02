#!/bin/sh
# Check at recipe execution time so help, clean and make -n need no daemon.
set -eu

if ! docker_bin=$(command -v docker); then
    printf '%s\n' 'Docker is required for this build but was not found in PATH.' >&2
    exit 127
fi

if docker_error=$(LC_ALL=C "$docker_bin" info 2>&1); then
    exec "$docker_bin" "$@"
else
    docker_status=$?
fi

# Group membership alone is unreliable: rootless Docker and socket ACLs may work.
# Only a local socket permission error qualifies for automatic elevation.
case "$docker_error" in
    *"permission denied"*) ;;
    *) printf '%s\n' "$docker_error" >&2; exit "$docker_status" ;;
esac
case "$docker_error" in
    *"daemon socket"*|*"dial unix "*) ;;
    *) printf '%s\n' "$docker_error" >&2; exit "$docker_status" ;;
esac
if [ "$(id -u)" = 0 ]; then
    printf '%s\n' "$docker_error" >&2
    exit "$docker_status"
fi

# Preserve the user's daemon when sudo selects a different HOME/context.
if [ -n "${DOCKER_CONTEXT:-}" ]; then
    endpoint=$("$docker_bin" context inspect "$DOCKER_CONTEXT" --format '{{.Endpoints.docker.Host}}')
elif [ -n "${DOCKER_HOST:-}" ]; then
    endpoint=$DOCKER_HOST
else
    endpoint=$("$docker_bin" context inspect --format '{{.Endpoints.docker.Host}}')
fi
case "$endpoint" in
    unix://*) ;;
    *) printf '%s\n' "$docker_error" >&2; exit "$docker_status" ;;
esac
if ! command -v sudo >/dev/null 2>&1; then
    printf '%s\n' "$docker_error" 'Docker socket access requires sudo, but sudo was not found in PATH.' >&2
    exit "$docker_status"
fi

printf '%s\n' 'Docker socket access denied; running Docker with sudo (authentication may be required).' >&2
# sudo may remove build/context environment variables; pass them explicitly.
exec sudo env DOCKER_BUILDKIT="${DOCKER_BUILDKIT:-1}" DOCKER_CONTEXT= DOCKER_HOST="$endpoint" \
    "$docker_bin" --host "$endpoint" "$@"
