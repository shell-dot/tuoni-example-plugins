# Import the shared offline builder before building; see the repository README.
ARG BUILDER_IMAGE=tuoni-plugin-builder:0.15.0-gradle9.7.1-v1

FROM --platform=linux/amd64 ${BUILDER_IMAGE} AS toolchains

# Build the .NET execunit without its Windows-only post-build event.
FROM scratch AS csharp-build
COPY --from=toolchains /opt/tuoni/toolchains/mono/ /
ENV PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
WORKDIR /build/exec-code/win
COPY exec-code/win/ .
RUN --network=none set -eu; \
    for format in shellcode dotnet-exe dotnet-dll; do \
        msbuild listener-execunit.csproj /p:Configuration=Release /p:PostBuildEvent= /p:ExecUnitFormat="$format"; \
    done

# Produce the execunit artifact using the bundled converter, as in the examples.
FROM scratch AS shellcode-build
COPY --from=toolchains /opt/tuoni/toolchains/windows/ /
ENV PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
ENV WINEDEBUG=-all \
    WINEDLLOVERRIDES=mscoree,mshtml= \
    WINEARCH=win64
WORKDIR /build/exec-code/win
COPY --from=csharp-build /build/exec-code/win/ .
COPY --from=toolchains /opt/tuoni/tools/donut.exe ./donut.exe
RUN --network=none wine ./donut.exe -z 1 -e 1 \
        -o bin/Release/listener-execunit-template.shellcode \
        -i bin/Release/listener-execunit-template.exe \
    && test -s bin/Release/listener-execunit-template.shellcode

# Build the Linux x64 native execunit with the same ABI as the examples.
FROM scratch AS linux-build
COPY --from=toolchains /opt/tuoni/toolchains/linux/ /
ENV PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
WORKDIR /build/exec-code/linux
COPY exec-code/linux/ .
RUN --network=none bash ./build_linux.sh

FROM scratch AS linux-artifacts
COPY --from=linux-build /build/exec-code/linux/build/listener-linux.native64_so \
     /listener-linux.native64_so

# Cross-compile Windows x86/x64 native DLLs and verify their loader contract.
FROM scratch AS windows-native-build
COPY --from=toolchains /opt/tuoni/toolchains/windows/ /
ENV PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
WORKDIR /build
COPY exec-code/win-native/ exec-code/win-native/
COPY scripts/verify_windows_native.py scripts/verify_windows_native.py
RUN --network=none bash exec-code/win-native/build_windows.sh

FROM scratch AS windows-native-artifacts
COPY --from=windows-native-build /build/exec-code/win-native/build/ /

# Package all rebuilt execunit formats into the Java plugin.
FROM toolchains AS java-build
WORKDIR /build
COPY --from=windows-native-build /build/exec-code/win-native/build/ exec-code/win-native/build/
COPY java-plugin/ java-plugin/
COPY --from=csharp-build /build/exec-code/win/ /build/exec-code/win/
COPY --from=shellcode-build /build/exec-code/win/bin/Release/listener-execunit-template.shellcode \
     /build/java-plugin/src/main/resources/listener.shellcode
COPY --from=linux-build /build/exec-code/linux/build/listener-linux.native64_so \
     /build/exec-code/linux/build/listener-linux.native64_so
WORKDIR /build/java-plugin
RUN --network=none chmod +x gradlew && ./gradlew build --offline --no-daemon

# Export managed formats and the legacy shellcode-input EXE without conversion.
FROM scratch AS dotnet-artifacts
COPY --from=csharp-build /build/exec-code/win/bin/Release/listener-execunit-template.exe \
     /listener-execunit-template.exe
COPY --from=csharp-build /build/exec-code/win/bin/Release/dotnet-exe/listener-execunit-template.dotnet_exe \
     /listener-execunit-template.dotnet_exe
COPY --from=csharp-build /build/exec-code/win/bin/Release/dotnet-dll/listener-execunit-template.dotnet_dll \
     /listener-execunit-template.dotnet_dll
COPY --from=csharp-build /build/exec-code/win/bin/Release/dotnet-dll/listener-execunit-template.dotnet_dll_method \
     /listener-execunit-template.dotnet_dll_method

# Export the full set of artifacts by default.
FROM scratch AS artifacts
COPY --from=windows-native-artifacts / /
COPY --from=dotnet-artifacts / /
COPY --from=shellcode-build /build/exec-code/win/bin/Release/listener-execunit-template.shellcode \
     /listener-execunit-template.shellcode
COPY --from=linux-build /build/exec-code/linux/build/listener-linux.native64_so \
     /listener-linux.native64_so
COPY --from=java-build /build/java-plugin/build/libs/listener-plugin-template-0.0.1.jar \
     /listener-plugin-template-0.0.1.jar
