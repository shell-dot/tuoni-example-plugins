#!/bin/sh
# Arguments are the project's Docker command, including any launcher/overrides.
set -eu

"$@" info >/dev/null
if "$@" buildx version >/dev/null 2>&1; then
    exit 0
fi
printf '%s\n' 'Docker Buildx is required to build these plugins.' >&2

# The distro alone is insufficient: Kali/Debian can use Docker CE or docker.io.
# Match the package owning the CLI, rather than guessing from the daemon version.
ID= ID_LIKE= PRETTY_NAME=
if [ -r /etc/os-release ]; then
    . /etc/os-release
fi
package=
case "$(uname -s): ${ID:-} ${ID_LIKE:-} " in
    Linux:*" debian "*|Linux:*" ubuntu "*|Linux:*" kali "*)
        if command -v apt-get >/dev/null 2>&1 && command -v dpkg-query >/dev/null 2>&1; then
            docker_bin=$(command -v docker || :)
            if [ -n "$docker_bin" ]; then
                docker_bin=$(readlink -f "$docker_bin" 2>/dev/null || printf '%s\n' "$docker_bin")
                owner=$(dpkg-query -S "$docker_bin" 2>/dev/null || :)
                case "$owner" in
                    docker-ce-cli:*) package=docker-buildx-plugin ;;
                    docker.io:*) package=docker-buildx ;;
                esac
            fi
        fi
        ;;
esac

if [ -z "$package" ]; then
    printf '%s\n' \
        "Could not select an automatic Buildx installation for ${PRETTY_NAME:-this environment} and its Docker CLI." \
        'Install Buildx using the instructions for your Docker installation: https://docs.docker.com/build/buildx/' \
        'Docker CE on Debian/Kali uses docker-buildx-plugin; distro docker.io uses docker-buildx.' >&2
    exit 1
fi

printf '%s\n' "Detected ${PRETTY_NAME:-$ID}, Docker CLI package ${owner%%:*}; Buildx package: $package." >&2
if [ "$(id -u)" = 0 ]; then
    privilege=
else
    privilege=sudo
fi
printf '%s\n' \
    "Install commands: ${privilege:+$privilege }apt-get update" \
    "                 ${privilege:+$privilege }apt-get install -y --no-remove $package" >&2
if [ -n "$privilege" ] && ! command -v sudo >/dev/null 2>&1; then
    printf '%s\n' 'sudo is unavailable; ask an administrator to run these commands.' >&2
    exit 1
fi

case "${BUILDX_INSTALL:-ask}" in
    1) ;;
    ask)
        if [ ! -t 0 ]; then
            printf '%s\n' 'No interactive input; install Buildx manually or rerun with BUILDX_INSTALL=1 to allow installation.' >&2
            exit 1
        fi
        printf 'Install %s now and continue the build? [y/N] ' "$package" >&2
        answer=
        read -r answer || :
        case "$answer" in
            y|Y|yes|YES) ;;
            *) printf '%s\n' 'Buildx installation declined; build stopped.' >&2; exit 1 ;;
        esac
        ;;
    0) printf '%s\n' 'Buildx installation disabled by BUILDX_INSTALL=0; build stopped.' >&2; exit 1 ;;
    *) printf '%s\n' 'BUILDX_INSTALL must be ask, 1, or 0.' >&2; exit 1 ;;
esac

# Install only the matching CLI plugin from existing repositories. --no-remove
# prevents apt from replacing Docker with a conflicting package family.
if $privilege apt-get update && $privilege apt-get install -y --no-remove "$package"; then
    if "$@" buildx version >/dev/null 2>&1; then
        printf '%s\n' 'Docker Buildx is available; continuing the build.' >&2
        exit 0
    fi
    printf '%s\n' 'Buildx is still unavailable through the build Docker command after installation.' \
        'Check docker buildx version (and sudo docker buildx version when Docker needs sudo).' >&2
else
    printf '%s\n' 'Buildx package installation failed; fix the apt/sudo error above and rerun the build.' >&2
fi
exit 1
