#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
output_dir="${1:-${script_dir}/build}"
mkdir -p "$output_dir"

"${CXX:-g++}" -std=c++11 -fPIC -shared -Os -pthread \
    -I"${script_dir}/common" \
    "${script_dir}/common/TLV.cpp" \
    "${script_dir}/common/CommunicationNamedPipes.cpp" \
    "${script_dir}/tcp-listener/Main.cpp" \
    -o "${output_dir}/tcp-listener-linux.native64_so"
