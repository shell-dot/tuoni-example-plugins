# Build once on the instructor machine; save/load the final image for the lab.
# Keep Gradle's cache in image layers so docker save includes every dependency.
FROM eclipse-temurin:21-jdk AS dependencies
ENV GRADLE_USER_HOME=/opt/gradle-home
WORKDIR /seed
COPY tools/docker/resolve-dependencies.gradle /seed/resolve-dependencies.gradle

# Copy only build definitions. Source edits do not invalidate the dependency image.
COPY echo-command-plugin/java-plugin/gradlew echo-command-plugin/java-plugin/*.kts echo-command-plugin/java-plugin/gradle.properties echo-command-plugin/java-plugin/
COPY echo-command-plugin/java-plugin/gradle/ echo-command-plugin/java-plugin/gradle/
COPY tcp-listener-plugin/java-plugin/gradlew tcp-listener-plugin/java-plugin/*.kts tcp-listener-plugin/java-plugin/gradle.properties tcp-listener-plugin/java-plugin/
COPY tcp-listener-plugin/java-plugin/gradle/ tcp-listener-plugin/java-plugin/gradle/
COPY dotnet-payload-plugin/java-plugin/gradlew dotnet-payload-plugin/java-plugin/*.kts dotnet-payload-plugin/java-plugin/gradle.properties dotnet-payload-plugin/java-plugin/
COPY dotnet-payload-plugin/java-plugin/gradle/ dotnet-payload-plugin/java-plugin/gradle/
COPY templates/command/java-plugin/gradlew templates/command/java-plugin/*.kts templates/command/java-plugin/
COPY templates/command/java-plugin/gradle/ templates/command/java-plugin/gradle/
COPY templates/listener/java-plugin/gradlew templates/listener/java-plugin/*.kts templates/listener/java-plugin/
COPY templates/listener/java-plugin/gradle/ templates/listener/java-plugin/gradle/
COPY templates/payloads/java-plugin/gradlew templates/payloads/java-plugin/*.kts templates/payloads/java-plugin/
COPY templates/payloads/java-plugin/gradle/ templates/payloads/java-plugin/gradle/

RUN set -eu; \
    for project in echo-command-plugin tcp-listener-plugin dotnet-payload-plugin \
                   templates/command templates/listener templates/payloads; do \
        cd "/seed/$project/java-plugin"; \
        sh ./gradlew --no-daemon -I /seed/resolve-dependencies.gradle labDependencies; \
    done

# Prove the wrapper, plugins and dependency JARs work without network access.
RUN --network=none set -eu; \
    for project in echo-command-plugin tcp-listener-plugin dotnet-payload-plugin \
                   templates/command templates/listener templates/payloads; do \
        cd "/seed/$project/java-plugin"; \
        sh ./gradlew --offline --no-daemon -I /seed/resolve-dependencies.gradle labDependencies; \
    done

FROM eclipse-temurin:21-jdk AS java-builder
ENV GRADLE_USER_HOME=/opt/gradle-home
COPY --from=dependencies /opt/gradle-home/ /opt/gradle-home/
WORKDIR /build

# Keep the original toolchain distributions/ABIs. Their filesystems are bundled
# into the single transport image and extracted into independent build stages.
FROM mono:6 AS mono-tools

FROM ubuntu:18.04 AS linux-tools
ENV DEBIAN_FRONTEND=noninteractive
RUN if ! apt-get update; then \
        sed -i \
            -e 's|http://archive.ubuntu.com/ubuntu|http://old-releases.ubuntu.com/ubuntu|g' \
            -e 's|http://security.ubuntu.com/ubuntu|http://old-releases.ubuntu.com/ubuntu|g' \
            /etc/apt/sources.list; \
        apt-get update; \
    fi \
    && apt-get install -y --no-install-recommends g++ wine-stable wine64 \
    && rm -rf /var/lib/apt/lists/*

FROM debian:bookworm-slim AS windows-tools
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        g++-mingw-w64-i686-posix g++-mingw-w64-x86-64-posix python3 wine \
    && rm -rf /var/lib/apt/lists/*

# docker save/load now transports Java, Mono, Wine, GCC and MinGW together.
FROM java-builder AS builder
COPY --from=mono-tools / /opt/tuoni/toolchains/mono/
COPY --from=linux-tools / /opt/tuoni/toolchains/linux/
COPY --from=windows-tools / /opt/tuoni/toolchains/windows/

# Repository tooling and artifact inspection must also work in the image,
# rather than relying on tools installed on the instructor's workstation.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        make python3 git zip unzip file binutils \
    && rm -rf /var/lib/apt/lists/*
COPY echo-command-plugin/exec-code/win/donut.exe /opt/tuoni/tools/donut.exe
COPY tools/docker/check-builder.sh /usr/local/bin/check-tuoni-builder
RUN --network=none chmod +x /usr/local/bin/check-tuoni-builder \
    && check-tuoni-builder
