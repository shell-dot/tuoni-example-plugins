# Stage 1: Build the .NET commands with Mono, skipping the Windows post-build event
FROM mono:6 AS csharp-build
WORKDIR /build/exec-code/win
COPY exec-code/win/ .
RUN set -eu; \
    for command in echo echo-ongoing echo-ongoing-file echo-ongoing-more-data; do \
        msbuild "$command/$command.csproj" /p:Configuration=Release /p:PostBuildEvent=; \
    done

# Stage 2: Convert the commands with the bundled Windows Donut executable
FROM debian:bookworm-slim AS shellcode-build
RUN apt-get update \
    && apt-get install -y --no-install-recommends wine \
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
FROM debian:bookworm-slim AS linux-build
RUN apt-get update \
    && apt-get install -y --no-install-recommends g++ \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /build/exec-code/linux
COPY exec-code/linux/ .
RUN bash ./build_linux.sh

# Export Linux execunits without requiring a compiler on the host.
FROM scratch AS linux-artifacts
COPY --from=linux-build /build/exec-code/linux/build/ /

# Stage 4: Build the Gradle plugin JAR (embeds both platforms)
FROM eclipse-temurin:21-jdk AS java-build
WORKDIR /build
COPY --from=shellcode-build /build/exec-code/win/ exec-code/win/
COPY --from=linux-build /build/exec-code/linux/build/ exec-code/linux/build/
COPY java-plugin/ java-plugin/
WORKDIR /build/java-plugin
RUN chmod +x gradlew && ./gradlew build --no-daemon

# Export only the .NET executables when the build-dotnet Make target is used.
FROM scratch AS dotnet-artifacts
COPY --from=csharp-build /build/exec-code/win/echo/bin/Release/echo.exe /echo.exe
COPY --from=csharp-build /build/exec-code/win/echo-ongoing/bin/Release/echo-ongoing.exe /echo-ongoing.exe
COPY --from=csharp-build /build/exec-code/win/echo-ongoing-file/bin/Release/echo-ongoing-file.exe /echo-ongoing-file.exe
COPY --from=csharp-build /build/exec-code/win/echo-ongoing-more-data/bin/Release/echo-ongoing-more-data.exe /echo-ongoing-more-data.exe

# Export the full set of artifacts by default.
FROM scratch AS artifacts
COPY --from=shellcode-build /artifacts/ /
COPY --from=linux-build /build/exec-code/linux/build/ /
COPY --from=java-build \
     /build/java-plugin/build/libs/tuoni-example-plugin-echo-command-0.0.1.jar \
     /tuoni-example-plugin-echo-command-0.0.1.jar
