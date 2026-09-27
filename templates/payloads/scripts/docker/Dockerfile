# Build the payload program from the C# skeleton.
FROM mono:6 AS csharp-build
WORKDIR /build/exec-code
COPY exec-code/ .
RUN msbuild payload.csproj /p:Configuration=Release

# Build the Java plugin; payload serialization remains a TODO in this template.
FROM eclipse-temurin:21-jdk AS java-build
WORKDIR /build
COPY java-plugin/ java-plugin/
WORKDIR /build/java-plugin
RUN chmod +x gradlew && ./gradlew build --no-daemon

# Export only the .NET executable when the build-dotnet Make target is used.
FROM scratch AS dotnet-artifacts
COPY --from=csharp-build /build/exec-code/bin/Release/payload-template.exe \
     /payload-template.exe

# Export the full set of artifacts by default.
FROM scratch AS artifacts
COPY --from=csharp-build /build/exec-code/bin/Release/payload-template.exe \
     /payload-template.exe
COPY --from=java-build /build/java-plugin/build/libs/payload-plugin-template-0.0.1.jar \
     /payload-plugin-template-0.0.1.jar
