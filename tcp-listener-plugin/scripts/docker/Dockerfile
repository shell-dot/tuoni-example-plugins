# Stage 1: Build the .NET listener with Mono, skipping the Windows post-build event
FROM --platform=linux/amd64 mono:6 AS csharp-build
WORKDIR /build/exec-code/win
COPY exec-code/win/ .
RUN msbuild tcp-listener/tcp-listener.csproj /p:Configuration=Release /p:PostBuildEvent=

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
    && apt-get install -y --no-install-recommends wine \
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

# Stage 4: Build the Gradle plugin JAR (embeds both platforms)
FROM eclipse-temurin:21-jdk AS java-build
WORKDIR /build
COPY --from=shellcode-build /build/exec-code/win/tcp-listener/bin/Release/tcp-listener.shellcode \
     exec-code/win/tcp-listener/bin/Release/tcp-listener.shellcode
COPY --from=linux-build /build/exec-code/linux/build/tcp-listener-linux.native64_so \
     exec-code/linux/build/tcp-listener-linux.native64_so
COPY java-plugin/ java-plugin/
WORKDIR /build/java-plugin
RUN chmod +x gradlew && ./gradlew build --no-daemon

# Export only the .NET executable when the build-dotnet Make target is used.
FROM scratch AS dotnet-artifacts
COPY --from=csharp-build /build/exec-code/win/tcp-listener/bin/Release/tcp-listener.exe /tcp-listener.exe

# Export the full set of artifacts by default.
FROM scratch AS artifacts
COPY --from=shellcode-build /build/exec-code/win/tcp-listener/bin/Release/tcp-listener.exe \
     /tcp-listener.exe
COPY --from=shellcode-build /build/exec-code/win/tcp-listener/bin/Release/tcp-listener.shellcode \
     /tcp-listener.shellcode
COPY --from=linux-build /build/exec-code/linux/build/tcp-listener-linux.native64_so \
     /tcp-listener-linux.native64_so
COPY --from=java-build \
     /build/java-plugin/build/libs/tuoni-example-plugin-tcp-listener-0.0.1.jar \
     /tuoni-example-plugin-tcp-listener-0.0.1.jar
