# Import the shared offline builder before building; see the repository README.
ARG BUILDER_IMAGE=tuoni-plugin-builder:0.15.0-gradle9.7.1-v1

FROM --platform=linux/amd64 ${BUILDER_IMAGE} AS toolchains

# Build the payload program from the C# skeleton.
FROM scratch AS csharp-build
COPY --from=toolchains /opt/tuoni/toolchains/mono/ /
ENV PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
WORKDIR /build/exec-code
COPY exec-code/ .
RUN --network=none msbuild payload.csproj /p:Configuration=Release

# Build the Java plugin; payload serialization remains a TODO in this template.
# This stage compiles the server-side builder separately from the payload program above.
# If serialization needs bundled program bytes, add an explicit resource-copy/package step
# matching the loader used by TemplatePayload; exporting an EXE does not embed it in this JAR.
FROM toolchains AS java-build
WORKDIR /build
COPY java-plugin/ java-plugin/
WORKDIR /build/java-plugin
RUN --network=none chmod +x gradlew && ./gradlew build --offline --no-daemon

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
