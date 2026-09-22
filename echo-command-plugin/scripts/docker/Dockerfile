# Stage 1: Build the .NET commands with Mono, skipping the Windows post-build event
FROM mono:6 AS csharp-build
WORKDIR /build/exec-code
COPY exec-code/ .
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
WORKDIR /build/exec-code
COPY --from=csharp-build /build/exec-code/ .
RUN set -eu; \
    mkdir -p /artifacts; \
    for command in echo echo-ongoing echo-ongoing-file echo-ongoing-more-data; do \
        wine ./donut.exe -z 1 -e 1 \
            -o "$command/bin/Release/$command.shellcode" \
            -i "$command/bin/Release/$command.exe"; \
        test -s "$command/bin/Release/$command.shellcode"; \
        cp "$command/bin/Release/$command.exe" "$command/bin/Release/$command.shellcode" /artifacts/; \
    done

# Stage 3: Build the Gradle plugin JAR (embeds the rebuilt shellcodes)
FROM eclipse-temurin:21-jdk AS java-build
WORKDIR /build
COPY --from=shellcode-build /build/exec-code/ exec-code/
COPY java-plugin/ java-plugin/
WORKDIR /build/java-plugin
RUN chmod +x gradlew && ./gradlew build --no-daemon

# Stage 4: Minimal image with just the artifacts for extraction
FROM scratch AS artifacts
COPY --from=shellcode-build /artifacts/ /
COPY --from=java-build \
     /build/java-plugin/build/libs/tuoni-example-plugin-echo-command-0.0.1.jar \
     /tuoni-example-plugin-echo-command-0.0.1.jar
