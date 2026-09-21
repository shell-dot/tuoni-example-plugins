# Stage 1: Build the .NET agent with Mono
FROM mono:6 AS csharp-build
WORKDIR /build/exec-code
COPY exec-code/ .
RUN msbuild dotnet-agent.csproj /p:Configuration=Release

# Stage 2: Build the Gradle plugin JAR (embeds the EXE)
FROM eclipse-temurin:21-jdk AS java-build
WORKDIR /build

# Place EXE where Gradle's processResources expects it (../exec-code/bin/Release/)
COPY --from=csharp-build /build/exec-code/bin/Release/dotnet-agent.exe \
     exec-code/bin/Release/dotnet-agent.exe

# Copy Gradle project
COPY java-plugin/ java-plugin/

WORKDIR /build/java-plugin
RUN chmod +x gradlew && ./gradlew build --no-daemon

# Stage 3: Minimal image with just the artifacts for extraction
FROM scratch AS artifacts
COPY --from=csharp-build /build/exec-code/bin/Release/dotnet-agent.exe \
     /dotnet-agent.exe
COPY --from=java-build \
     /build/java-plugin/build/libs/tuoni-example-plugin-dotnet-payload-0.0.1.jar \
     /tuoni-example-plugin-dotnet-payload-0.0.1.jar
