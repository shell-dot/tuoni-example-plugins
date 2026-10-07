#!/bin/sh
# Resolve Tuoni before copying anything; keep each installation's user context.
set -eu

if [ "$#" -lt 2 ] || [ "$#" -gt 4 ]; then
    printf '%s\n' 'Usage: install-plugin.sh JAR PLUGIN_DIR [TUONI]' >&2
    exit 2
fi

jar=$1
plugin_dir=$2
tuoni_command=${3:-tuoni}
uid=$(id -u)

# Login shells may change directory. Preserve all paths across re-execution.
case "$jar" in /*) ;; *) jar=$PWD/$jar ;; esac
case "$plugin_dir" in /*) ;; *) plugin_dir=$PWD/$plugin_dir ;; esac
case "$0" in /*) installer=$0 ;; *) installer=$PWD/$0 ;; esac
case "$tuoni_command" in
    /*) ;;
    */*) tuoni_command=$PWD/$tuoni_command ;;
esac

if [ ! -f "$jar" ]; then
    printf 'Plugin JAR not found: %s\n' "$jar" >&2
    exit 1
fi

if ! tuoni_bin=$(command -v "$tuoni_command"); then
    # Tuoni's setup adds its directory to .bashrc, which make does not source.
    # Re-enter the installer instead of parsing output from shell startup files.
    if [ "${4:-}" != --login ] && command -v bash >/dev/null 2>&1; then
        exec bash -lic 'exec /bin/sh "$@"' install-plugin \
            "$installer" "$jar" "$plugin_dir" "$tuoni_command" --login
    fi

    if [ "$uid" = 0 ]; then
        # Also handle the standard installation before its PATH update is loaded.
        if [ "$tuoni_command" = tuoni ] && [ -x /srv/tuoni/tuoni ]; then
            tuoni_bin=/srv/tuoni/tuoni
        else
            printf 'Tuoni command not found for the current user or root: %s. Set TUONI=/path/to/tuoni.\n' "$tuoni_command" >&2
            exit 127
        fi
    elif command -v sudo >/dev/null 2>&1; then
        exec sudo -H bash -lic 'exec /bin/sh "$@"' install-plugin \
            "$installer" "$jar" "$plugin_dir" "$tuoni_command" --login
    else
        printf 'Tuoni command not found: %s; sudo is required to check root\047s installation. Set TUONI=/path/to/tuoni.\n' "$tuoni_command" >&2
        exit 127
    fi
fi

destination=$plugin_dir/${jar##*/}
if [ "$uid" = 0 ] || { [ -w "$plugin_dir" ] && { [ ! -e "$destination" ] || [ -w "$destination" ]; }; }; then
    cp -- "$jar" "$plugin_dir/"
elif command -v sudo >/dev/null 2>&1; then
    sudo cp -- "$jar" "$plugin_dir/"
else
    printf 'Installing into %s requires sudo, but sudo was not found in PATH.\n' "$plugin_dir" >&2
    exit 1
fi

"$tuoni_bin" restart
printf '[+] Installed %s to %s and restarted Tuoni.\n' "${jar##*/}" "$plugin_dir"
