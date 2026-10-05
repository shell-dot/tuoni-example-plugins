# Stage 1: Build the .NET commands with Mono, skipping the Windows post-build event
FROM --platform=linux/amd64 mono:6 AS csharp-build
WORKDIR /build/exec-code/win
COPY exec-code/win/ .
RUN set -eu; \
    for command in echo echo-ongoing echo-ongoing-file echo-ongoing-more-data; do \
        for format in shellcode dotnet-exe dotnet-dll; do \
            msbuild "$command/$command.csproj" /p:Configuration=Release /p:PostBuildEvent= /p:ExecUnitFormat="$format"; \
        done; \
    done

# Stage 2: Convert the commands with the bundled Windows Donut executable
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
RUN set -eu; \
    mkdir -p /artifacts; \
    for command in echo echo-ongoing echo-ongoing-file echo-ongoing-more-data; do \
        wine ./donut.exe -z 1 -e 1 \
            -o "$command/bin/Release/$command.shellcode" \
            -i "$command/bin/Release/$command.exe"; \
        test -s "$command/bin/Release/$command.shellcode"; \
        cp "$command/bin/Release/$command.exe" "$command/bin/Release/$command.shellcode" /artifacts/; \
    done

# Stage 3: Build Linux x64 execunits using the same ABI as the default Linux commands.
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

# Export Linux execunits without requiring a compiler on the host.
FROM scratch AS linux-artifacts
COPY --from=linux-build /build/exec-code/linux/build/ /

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
COPY --from=linux-build /build/exec-code/linux/build/ exec-code/linux/build/
COPY --from=windows-native-build /build/exec-code/win-native/build/ exec-code/win-native/build/
COPY java-plugin/ java-plugin/
WORKDIR /build/java-plugin
RUN chmod +x gradlew && ./gradlew build --no-daemon

# Export managed formats and the legacy shellcode-input EXEs without conversion.
FROM scratch AS dotnet-artifacts
COPY --from=csharp-build /build/exec-code/win/echo/bin/Release/echo.exe /echo.exe
COPY --from=csharp-build /build/exec-code/win/echo/bin/Release/dotnet-exe/echo.dotnet_exe /echo.dotnet_exe
COPY --from=csharp-build /build/exec-code/win/echo/bin/Release/dotnet-dll/echo.dotnet_dll /echo.dotnet_dll
COPY --from=csharp-build /build/exec-code/win/echo/bin/Release/dotnet-dll/echo.dotnet_dll_method /echo.dotnet_dll_method
COPY --from=csharp-build /build/exec-code/win/echo-ongoing/bin/Release/echo-ongoing.exe /echo-ongoing.exe
COPY --from=csharp-build /build/exec-code/win/echo-ongoing/bin/Release/dotnet-exe/echo-ongoing.dotnet_exe /echo-ongoing.dotnet_exe
COPY --from=csharp-build /build/exec-code/win/echo-ongoing/bin/Release/dotnet-dll/echo-ongoing.dotnet_dll /echo-ongoing.dotnet_dll
COPY --from=csharp-build /build/exec-code/win/echo-ongoing/bin/Release/dotnet-dll/echo-ongoing.dotnet_dll_method /echo-ongoing.dotnet_dll_method
COPY --from=csharp-build /build/exec-code/win/echo-ongoing-file/bin/Release/echo-ongoing-file.exe /echo-ongoing-file.exe
COPY --from=csharp-build /build/exec-code/win/echo-ongoing-file/bin/Release/dotnet-exe/echo-ongoing-file.dotnet_exe /echo-ongoing-file.dotnet_exe
COPY --from=csharp-build /build/exec-code/win/echo-ongoing-file/bin/Release/dotnet-dll/echo-ongoing-file.dotnet_dll /echo-ongoing-file.dotnet_dll
COPY --from=csharp-build /build/exec-code/win/echo-ongoing-file/bin/Release/dotnet-dll/echo-ongoing-file.dotnet_dll_method /echo-ongoing-file.dotnet_dll_method
COPY --from=csharp-build /build/exec-code/win/echo-ongoing-more-data/bin/Release/echo-ongoing-more-data.exe /echo-ongoing-more-data.exe
COPY --from=csharp-build /build/exec-code/win/echo-ongoing-more-data/bin/Release/dotnet-exe/echo-ongoing-more-data.dotnet_exe /echo-ongoing-more-data.dotnet_exe
COPY --from=csharp-build /build/exec-code/win/echo-ongoing-more-data/bin/Release/dotnet-dll/echo-ongoing-more-data.dotnet_dll /echo-ongoing-more-data.dotnet_dll
COPY --from=csharp-build /build/exec-code/win/echo-ongoing-more-data/bin/Release/dotnet-dll/echo-ongoing-more-data.dotnet_dll_method /echo-ongoing-more-data.dotnet_dll_method

# Export the full set of artifacts by default.
FROM scratch AS artifacts
COPY --from=windows-native-artifacts / /
COPY --from=dotnet-artifacts / /
COPY --from=shellcode-build /artifacts/ /
COPY --from=linux-build /build/exec-code/linux/build/ /
COPY --from=java-build \
     /build/java-plugin/build/libs/tuoni-example-plugin-echo-command-0.0.1.jar \
     /tuoni-example-plugin-echo-command-0.0.1.jar
