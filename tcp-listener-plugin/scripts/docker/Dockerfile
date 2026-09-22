# Stage 1: Build the .NET listener with Mono, skipping the Windows post-build event
FROM mono:6 AS csharp-build
WORKDIR /build/exec-code
COPY exec-code/ .
RUN msbuild tcp-listener/tcp-listener.csproj /p:Configuration=Release /p:PostBuildEvent=

# Stage 2: Convert the listener with the bundled Windows Donut executable
FROM debian:bookworm-slim AS shellcode-build
RUN apt-get update \
    && apt-get install -y --no-install-recommends wine \
    && rm -rf /var/lib/apt/lists/*
ENV WINEDEBUG=-all \
    WINEDLLOVERRIDES=mscoree,mshtml= \
    WINEARCH=win64
WORKDIR /build/exec-code
COPY --from=csharp-build /build/exec-code/ .
RUN wine ./donut.exe -z 1 -e 1 \
        -o tcp-listener/bin/Release/tcp-listener.shellcode \
        -i tcp-listener/bin/Release/tcp-listener.exe \
    && test -s tcp-listener/bin/Release/tcp-listener.shellcode

# Stage 3: Build the Gradle plugin JAR (embeds the rebuilt shellcode)
FROM eclipse-temurin:21-jdk AS java-build
WORKDIR /build
COPY --from=shellcode-build /build/exec-code/tcp-listener/bin/Release/tcp-listener.shellcode \
     exec-code/tcp-listener/bin/Release/tcp-listener.shellcode
COPY java-plugin/ java-plugin/
WORKDIR /build/java-plugin
RUN chmod +x gradlew && ./gradlew build --no-daemon

# Stage 4: Minimal image with just the artifacts for extraction
FROM scratch AS artifacts
COPY --from=shellcode-build /build/exec-code/tcp-listener/bin/Release/tcp-listener.exe \
     /tcp-listener.exe
COPY --from=shellcode-build /build/exec-code/tcp-listener/bin/Release/tcp-listener.shellcode \
     /tcp-listener.shellcode
COPY --from=java-build \
     /build/java-plugin/build/libs/tuoni-example-plugin-tcp-listener-0.0.1.jar \
     /tuoni-example-plugin-tcp-listener-0.0.1.jar
