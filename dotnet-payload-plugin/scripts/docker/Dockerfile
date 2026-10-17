# Import the shared offline builder before building; see the repository README.
ARG BUILDER_IMAGE=tuoni-plugin-builder:0.15.0-gradle9.7.1-v1

FROM --platform=linux/amd64 ${BUILDER_IMAGE} AS toolchains

# Stage 1: Build the .NET agent with Mono
FROM scratch AS csharp-build
COPY --from=toolchains /opt/tuoni/toolchains/mono/ /
ENV PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
WORKDIR /build/exec-code
COPY exec-code/ .
RUN --network=none msbuild dotnet-agent.csproj /p:Configuration=Release

# Stage 2: Build the Gradle plugin JAR (embeds the EXE)
FROM toolchains AS java-build
WORKDIR /build

# Place EXE where Gradle's processResources expects it (../exec-code/bin/Release/)
COPY --from=csharp-build /build/exec-code/bin/Release/dotnet-agent.exe \
     exec-code/bin/Release/dotnet-agent.exe

# Copy Gradle project
COPY java-plugin/ java-plugin/

WORKDIR /build/java-plugin
RUN --network=none chmod +x gradlew && ./gradlew build --offline --no-daemon

# Export only the .NET executable when the build-dotnet Make target is used.
FROM scratch AS dotnet-artifacts
COPY --from=csharp-build /build/exec-code/bin/Release/dotnet-agent.exe /dotnet-agent.exe

# Export the full set of artifacts by default.
FROM scratch AS artifacts
COPY --from=csharp-build /build/exec-code/bin/Release/dotnet-agent.exe \
     /dotnet-agent.exe
COPY --from=java-build \
     /build/java-plugin/build/libs/tuoni-example-plugin-dotnet-payload-0.0.1.jar \
     /tuoni-example-plugin-dotnet-payload-0.0.1.jar
