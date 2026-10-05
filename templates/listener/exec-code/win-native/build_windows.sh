#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
output_dir="${1:-${script_dir}/build}"
mkdir -p "$output_dir"

units=(listener)
utilities=(CommunicationNamedPipes TLV Conversions)
for bits in 32 64; do
    if [ "$bits" = 32 ]; then
        compiler="${CXX_X86:-i686-w64-mingw32-g++-posix}"
    else
        compiler="${CXX_X64:-x86_64-w64-mingw32-g++-posix}"
    fi
    flags=(-std=c++11 -Os -Wall -Wextra -D_WIN32_WINNT=0x0601 -DWIN32_LEAN_AND_MEAN -DNOMINMAX)
    object_dir="${script_dir}/obj/${bits}"
    mkdir -p "$object_dir"
    objects=()
    # Compile copied utilities separately: upstream warnings must not require
    # source rewrites. Example entrypoints still compile with -Werror.
    for source in "${utilities[@]}"; do
        object="${object_dir}/${source}.o"
        "$compiler" "${flags[@]}" -c "${script_dir}/exec-unit-utils/${source}.cpp" -o "$object"
        objects+=("$object")
    done
    for unit in "${units[@]}"; do
        "$compiler" "${flags[@]}" -Werror -shared \
            -static -static-libgcc -static-libstdc++ -Wl,--exclude-all-symbols \
            "${script_dir}/${unit}/Main.cpp" "${objects[@]}" "${script_dir}/exports.def" \
            -o "${output_dir}/${unit}.native${bits}_dll"
    done
done
python3 "${script_dir}/../../scripts/verify_windows_native.py" \
    "${output_dir}/"*.native32_dll "${output_dir}/"*.native64_dll
