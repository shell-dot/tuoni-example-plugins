# Stage 1: Build the .NET listener with Mono, skipping the Windows post-build event
FROM --platform=linux/amd64 mono:6 AS csharp-build
WORKDIR /build/exec-code/win
COPY exec-code/win/ .
RUN set -eu; \
    for format in shellcode dotnet-exe dotnet-dll; do \
        msbuild tcp-listener/tcp-listener.csproj /p:Configuration=Release /p:PostBuildEvent= /p:ExecUnitFormat="$format"; \
    done

# Stage 2: Convert the listener with the bundled Windows Donut executable
FROM --platform=linux/amd64 ubuntu:18.04 AS shellcode-build
ENV DEBIAN_FRONTEND=noninteractive
RUN if ! apt-get update; then \
        sed -i \
            -e 's|http://archive.ubuntu.com/ubuntu|http://old-releases.ubuntu.com/ubuntu|g' \
            -e 's|http://security.ubuntu.com/ubuntu|http://old-releases.ubuntu.com/ubuntu|g' \
            /etc/apt/sources.list; \
        apt-get update; \
    fi \
    && apt-get install -y --no-install-recommends wine-stable wine64 \
    && rm -rf /var/lib/apt/lists/*
ENV WINEDEBUG=-all \
    WINEDLLOVERRIDES=mscoree,mshtml= \
    WINEARCH=win64
WORKDIR /build/exec-code/win
COPY --from=csharp-build /build/exec-code/win/ .
RUN wine ./donut.exe -z 1 -e 1 \
        -o tcp-listener/bin/Release/tcp-listener.shellcode \
        -i tcp-listener/bin/Release/tcp-listener.exe \
    && test -s tcp-listener/bin/Release/tcp-listener.shellcode

# Stage 3: Build the Linux x64 execunit.
FROM --platform=linux/amd64 ubuntu:18.04 AS linux-build
ENV DEBIAN_FRONTEND=noninteractive
RUN if ! apt-get update; then \
        sed -i \
            -e 's|http://archive.ubuntu.com/ubuntu|http://old-releases.ubuntu.com/ubuntu|g' \
            -e 's|http://security.ubuntu.com/ubuntu|http://old-releases.ubuntu.com/ubuntu|g' \
            /etc/apt/sources.list; \
        apt-get update; \
    fi \
    && apt-get install -y --no-install-recommends g++ \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /build/exec-code/linux
COPY exec-code/linux/ .
RUN bash ./build_linux.sh

# Export the Linux execunit without requiring a compiler on the host.
FROM scratch AS linux-artifacts
COPY --from=linux-build /build/exec-code/linux/build/tcp-listener-linux.native64_so \
     /tcp-listener-linux.native64_so

# Cross-compile Windows x86/x64 native DLLs and verify their loader contract.
FROM debian:bookworm-slim AS windows-native-build
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        g++-mingw-w64-i686-posix g++-mingw-w64-x86-64-posix python3 \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /build
COPY exec-code/win-native/ exec-code/win-native/
COPY scripts/verify_windows_native.py scripts/verify_windows_native.py
RUN bash exec-code/win-native/build_windows.sh

FROM scratch AS windows-native-artifacts
COPY --from=windows-native-build /build/exec-code/win-native/build/ /

# Package all rebuilt execunit formats into the Java plugin.
FROM eclipse-temurin:21-jdk AS java-build
WORKDIR /build
COPY --from=shellcode-build /build/exec-code/win/ exec-code/win/
COPY --from=linux-build /build/exec-code/linux/build/tcp-listener-linux.native64_so \
     exec-code/linux/build/tcp-listener-linux.native64_so
COPY --from=windows-native-build /build/exec-code/win-native/build/ exec-code/win-native/build/
COPY java-plugin/ java-plugin/
WORKDIR /build/java-plugin
RUN chmod +x gradlew && ./gradlew build --no-daemon

# Export managed formats and the legacy shellcode-input EXE without conversion.
FROM scratch AS dotnet-artifacts
COPY --from=csharp-build /build/exec-code/win/tcp-listener/bin/Release/tcp-listener.exe /tcp-listener.exe
COPY --from=csharp-build /build/exec-code/win/tcp-listener/bin/Release/dotnet-exe/tcp-listener.dotnet_exe /tcp-listener.dotnet_exe
COPY --from=csharp-build /build/exec-code/win/tcp-listener/bin/Release/dotnet-dll/tcp-listener.dotnet_dll /tcp-listener.dotnet_dll
COPY --from=csharp-build /build/exec-code/win/tcp-listener/bin/Release/dotnet-dll/tcp-listener.dotnet_dll_method /tcp-listener.dotnet_dll_method

# Export the full set of artifacts by default.
FROM scratch AS artifacts
COPY --from=windows-native-artifacts / /
COPY --from=dotnet-artifacts / /
COPY --from=shellcode-build /build/exec-code/win/tcp-listener/bin/Release/tcp-listener.shellcode \
     /tcp-listener.shellcode
COPY --from=linux-build /build/exec-code/linux/build/tcp-listener-linux.native64_so \
     /tcp-listener-linux.native64_so
COPY --from=java-build \
     /build/java-plugin/build/libs/tuoni-example-plugin-tcp-listener-0.0.1.jar \
     /tuoni-example-plugin-tcp-listener-0.0.1.jar
