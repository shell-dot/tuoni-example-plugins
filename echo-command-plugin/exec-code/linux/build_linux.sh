#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
output_dir="${1:-${script_dir}/build}"
mkdir -p "$output_dir"

commands=(echo echo-ongoing echo-ongoing-file echo-ongoing-more-data)
for name in "${commands[@]}"; do
    "${CXX:-g++}" -std=c++11 -fPIC -shared -Os -pthread \
        -I"${script_dir}/common" \
        "${script_dir}/common/TLV.cpp" \
        "${script_dir}/common/CommunicationNamedPipes.cpp" \
        "${script_dir}/${name}/Main.cpp" \
        -o "${output_dir}/${name}-linux.native64_so"
done
