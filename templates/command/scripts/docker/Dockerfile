# Build the .NET execunit without its Windows-only post-build event.
FROM mono:6 AS csharp-build
WORKDIR /build/exec-code
COPY exec-code/ .
RUN msbuild command-execunit.csproj /p:Configuration=Release /p:PostBuildEvent=

# Produce the execunit artifact using the bundled converter, as in the examples.
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
        -o bin/Release/command-execunit-template.shellcode \
        -i bin/Release/command-execunit-template.exe \
    && test -s bin/Release/command-execunit-template.shellcode

# Package the rebuilt artifact at the classpath path used by TemplateCommand.
FROM eclipse-temurin:21-jdk AS java-build
WORKDIR /build
COPY java-plugin/ java-plugin/
COPY --from=shellcode-build /build/exec-code/bin/Release/command-execunit-template.shellcode \
     /build/java-plugin/src/main/resources/command.shellcode
WORKDIR /build/java-plugin
RUN chmod +x gradlew && ./gradlew build --no-daemon

# Export only the .NET executable when the build-dotnet Make target is used.
FROM scratch AS dotnet-artifacts
COPY --from=csharp-build /build/exec-code/bin/Release/command-execunit-template.exe \
     /command-execunit-template.exe

# Export the full set of artifacts by default.
FROM scratch AS artifacts
COPY --from=shellcode-build /build/exec-code/bin/Release/command-execunit-template.exe \
     /command-execunit-template.exe
COPY --from=shellcode-build /build/exec-code/bin/Release/command-execunit-template.shellcode \
     /command-execunit-template.shellcode
COPY --from=java-build /build/java-plugin/build/libs/command-plugin-template-0.0.1.jar \
     /command-plugin-template-0.0.1.jar
