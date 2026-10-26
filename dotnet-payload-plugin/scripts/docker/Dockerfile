ARG BUILDER_IMAGE

# Stage 1: Build the .NET agent with Mono
FROM mono:6 AS csharp-build
WORKDIR /build/exec-code
COPY exec-code/ .
RUN msbuild dotnet-agent.csproj /p:Configuration=Release

# Stage 2: Build the Gradle plugin JAR (embeds the EXE)
FROM ${BUILDER_IMAGE} AS gradle-seed

FROM gradle-seed AS java-build
ENV GRADLE_USER_HOME=/opt/gradle-home
WORKDIR /build

# Place EXE where Gradle's processResources expects it (../exec-code/bin/Release/)
COPY --from=csharp-build /build/exec-code/bin/Release/dotnet-agent.exe \
     exec-code/bin/Release/dotnet-agent.exe

# Copy Gradle project
COPY java-plugin/ java-plugin/

WORKDIR /build/java-plugin
ARG GRADLE_CACHE_ID
RUN --mount=type=cache,id=${GRADLE_CACHE_ID},target=/opt/gradle-home,from=gradle-seed,source=/opt/gradle-home,sharing=locked \
    sh ./gradlew build --no-daemon --build-cache

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
