#!/bin/sh
# Check the contents of the portable image without a repository mount or network.
set -eu

for tool in java javac make python3 git zip unzip file nm objdump readelf bash sed awk tar chroot; do
    command -v "$tool" >/dev/null
done
python3 -c 'import curses, ctypes, json, subprocess, xml.etree.ElementTree, zipfile'
printf '%s\n' 'PASS Java/JDK, Make, Python (including curses), Git, ZIP and artifact inspection tools'

# Mono itself needs /proc, which is mounted in the extracted build stage rather
# than inside this storage directory. Check its tools and reference assemblies.
chroot /opt/tuoni/toolchains/mono /bin/sh -c \
    'command -v mono && command -v msbuild && test -s /usr/lib/mono/4.6.2-api/mscorlib.dll && test -s /usr/lib/mono/msbuild/Current/bin/Roslyn/csc.exe' >/dev/null
printf '%s\n' 'PASS Mono/MSBuild and .NET Framework reference assemblies'
chroot /opt/tuoni/toolchains/linux /bin/sh -c 'g++ --version && /usr/lib/wine/wine64 --version' >/dev/null
printf '%s\n' 'PASS Ubuntu Linux C++ compiler and Wine64'
chroot /opt/tuoni/toolchains/windows /bin/sh -c \
    'i686-w64-mingw32-g++-posix --version && x86_64-w64-mingw32-g++-posix --version && python3 --version && test -x /usr/lib/wine/wine64 && test -s /usr/lib/x86_64-linux-gnu/wine/x86_64-unix/ntdll.so' >/dev/null
printf '%s\n' 'PASS Windows x86/x64 MinGW compilers, Python and Wine64'

python3 - <<'PY'
import os
from pathlib import Path

home = Path(os.environ['GRADLE_USER_HOME'])
assert any(home.glob('wrapper/dists/*/*/*/bin/gradle')), 'Missing cached Gradle distribution'
assert any(home.glob('caches/modules-2/files-2.1/com.shelldot/tuoni-plugin-sdk/*/*/*.jar')), 'Missing cached Tuoni SDK'
assert Path('/opt/tuoni/tools/donut.exe').stat().st_size > 0, 'Missing Donut converter'
print('PASS cached Gradle distribution, Maven SDK artifacts and bundled Donut converter')
PY
