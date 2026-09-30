# Building and checking the listener plugin

Run commands from the plugin root containing `java-plugin/` and `exec-code/`. Use the actual renamed paths in a generated plugin. Preserve its SDK version, Java target, native ABI, and existing build setup unless the requested change requires updating them.

## Choose a build route and check its tools

| Route | Required tools and checks | Compatibility |
| --- | --- | --- |
| Java locally | `java -version`, `javac -version`, and the checked-in Gradle wrapper | JDK 21+; `options.release = 21` in `java-plugin/build.gradle.kts`. Set `JAVA_HOME` to the selected JDK if necessary. The first wrapper/dependency download needs network access; use `--offline` only when cached. |
| Windows locally | In Developer PowerShell, `Get-Command msbuild` or `Get-Command dotnet`; use the .NET Framework 4.6.2 targeting pack | The `.csproj` targets .NET Framework 4.6.2. This does not imply support for every modern C# feature or .NET API. Check the compiler used by the selected MSBuild; keep syntax compatible with the Docker Mono compiler too. |
| Linux locally | In Linux/WSL, `command -v g++` and `g++ --version` | `exec-code/linux/build_linux.sh` uses `-std=c++11`; do not introduce C++14/17 APIs such as `std::make_unique` or `std::optional` without deliberately updating the supported toolchain. The library must remain Linux x64 compatible. |
| Docker | In Linux/WSL, `make --version`, `docker version`, and `docker info --format '{{.OSType}}'` returning `linux` | Use GNU Make, a Linux/WSL shell, and standard Unix utilities. The recipes do not run directly in PowerShell/CMD. Docker must be accessible from that shell. |
| Archive checks | `python --version` or `python3 --version` | Python 3; the check below uses only its standard library. |

A missing executable on `PATH` is a tool-discovery issue: try the installed JDK's `bin/` tools or Visual Studio Developer PowerShell before declaring that route unavailable. Do not change source code or remove required resources just to bypass an unavailable compiler.

## Java dependencies and compilation

The SDK exposes `JsonConfiguration.toJSON()` but supplies no JSON parser. Keep the SDK dependency as `compileOnly`; Tuoni supplies it. Bundle every other runtime dependency in the distributable JAR.

For a fresh template using Jackson, merge the following into the existing blocks of `java-plugin/build.gradle.kts`. These versions match this repository's Gradle 9.7.1 wrapper and example projects. Retain the existing `group`, `version`, repositories, Java release, complete `Plugin-*` manifest, and `processResources` checks. Reuse an established parser or shading setup instead of adding a second one.

```kotlin
plugins {
    java
    id("com.gradleup.shadow") version "9.6.1"
}

dependencies {
    compileOnly("com.shelldot:tuoni-plugin-sdk:0.15.0")
    implementation("tools.jackson.core:jackson-databind:3.2.2")
}

tasks.jar {
    archiveClassifier.set("shallow")
    // Keep the template's existing manifest { attributes(...) } here.
}

tasks.shadowJar {
    archiveClassifier.set("")
    // Shadow inherits the existing jar manifest in this version.
    filesMatching("META-INF/services/**") {
        duplicatesStrategy = DuplicatesStrategy.INCLUDE
    }
    mergeServiceFiles()
}

tasks.assemble {
    dependsOn(tasks.shadowJar)
}
```

Jackson 3 uses `tools.jackson.databind.*` imports, including `tools.jackson.databind.json.JsonMapper`; do not copy Jackson 2 databind imports. This example declares the dependency directly because the template has no `libs.jackson.databind` version-catalog alias. Keep the unclassified JAR as the distributable and the `-shallow.jar` as the dependency-free artifact. With the default project name/version, the distributable remains `listener-plugin-template-0.0.1.jar`.

If its name or version changes, update all of these together:

- `java-plugin/settings.gradle.kts`: `rootProject.name`; `java-plugin/build.gradle.kts`: `version` and any archive-name overrides.
- `Makefile`: `JAR_NAME`.
- `scripts/docker/Dockerfile`: the `artifacts` stage's JAR `COPY` source and destination.
- Documentation and verification scripts containing the full archive filename.

Preserve `META-INF/services/com.shelldot.tuoni.plugin.sdk.listener.ListenerPlugin`. Adding `implementation` alone does not bundle dependencies in the plain Java JAR.

Compile Java in PowerShell:

```powershell
.\java-plugin\gradlew.bat -p java-plugin compileJava
```

Or in a POSIX shell:

```sh
bash java-plugin/gradlew -p java-plugin compileJava
```

The wrapper path does not select the Gradle project; keep `-p java-plugin` from the plugin root. Compilation does not run the native resource checks or verify packaging.

### Inspect SDK signatures before adding hooks

Read the SDK version from `java-plugin/build.gradle.kts`. The dependency cache is under `GRADLE_USER_HOME`, or the user's `.gradle` directory when unset. Locate the matching JAR under `caches/modules-2/files-2.1/com.shelldot/tuoni-plugin-sdk/<version>/`; ignore `-sources.jar`. Then use the selected JDK's `javap`:

```text
javap -classpath "<absolute-sdk-jar>" com.shelldot.tuoni.plugin.sdk.listener.ListenerPlugin
```

Use `jar tf "<absolute-sdk-jar>"` to find other fully qualified class names, then inspect those exact types. Check constructors, return types and declared exceptions before calling or overriding a method. On PowerShell, a quoted executable path needs `&`, for example `& "$env:JAVA_HOME/bin/javap.exe" -classpath "<absolute-sdk-jar>" <fully-qualified-class>`.

## Adapting resources and dependencies from existing plugins

Use the [existing plugin map](existing-plugins.md) to locate a matching Java/native pair. Server modules use internal helpers and Gradle convention plugins that are not supplied by this standalone template. Adapt their data flow using the SDK and ordinary Java APIs; do not import internal modules to reproduce their payload format. The inspected server production build targets Java 25 while this template and SDK target Java 21. Verify library bytecode and APIs against the plugin's target; adding a server JAR can require a newer JVM even when the copied Java source looks compatible. Bundle declared runtime libraries and preserve the template's service descriptor.

### Resource selection

For each supported combination, check OS, **process** architecture, exec-unit type, resource path, loader entrypoint, and the actual artifact. Reject unsupported/unknown combinations at both capability selection and generation. Do not choose x64 solely because architecture is not x86. Add platforms or artifact types only when the request requires them and matching implementations exist.

If a requested extension adds .NET DLL exec-units, existing plugins read the companion `<artifact>.dotnet_dll_method` resource through `DotnetDllEntrypoint`. Preserve the generated entrypoint metadata and test it against the actual DLL; an obfuscated assembly cannot assume a hardcoded source method name. Windows native DLLs and POSIX libraries have different entrypoints/ABIs; inspect their loader contract rather than copying one export name everywhere. The fresh template does not claim these extra artifact types.

## Rebuild native resources

On Windows, use the solution so `$(SolutionDir)` is set for its post-build event:

```powershell
msbuild exec-code/win/listener-execunit.sln /t:Rebuild /p:Configuration=Release
```

`dotnet msbuild` with the same arguments is an alternative when the required targeting pack is installed. The post-build event in `exec-code/win/listener-execunit.csproj` converts `exec-code/win/bin/Release/listener-execunit-template.exe` into `listener-execunit-template.shellcode` beside the EXE and copies it to `java-plugin/src/main/resources/listener.shellcode`. The template contains `exec-code/win/donut.exe` for this step. A build using `/p:PostBuildEvent=` verifies C# compilation only and does not refresh the resource.

In Linux/WSL with g++, run:

```sh
bash exec-code/linux/build_linux.sh
```

This produces `exec-code/linux/build/listener-linux.native64_so`. Add new `.cpp` translation units to the compiler command in that script; add new C# files as `<Compile Include="..." />` entries in the `.csproj`. On Windows, use Linux/WSL or the Docker route; a Windows compiler's output is not a Linux library.

The Make targets have different results; run them in the Linux/WSL shell described above:

| Command | Result |
| --- | --- |
| `make build-linux` | Builds Linux in Docker and writes `exec-code/linux/build/listener-linux.native64_so` plus a copy under `build/`; suitable for a later local Gradle build. |
| `make build-dotnet` | Exports only `build/listener-execunit-template.exe`; it does not generate shellcode or a JAR. |
| `make build` | Builds both exec-units, converts Windows shellcode, and packages Java inside Docker; exports the JAR, EXE, shellcode and Linux library under `build/`. It does not refresh the local Gradle output or local native-resource paths. |

## Package and verify

For a local build, rebuild both native resources first, then run `bash java-plugin/gradlew -p java-plugin clean build` or `.\java-plugin\gradlew.bat -p java-plugin clean build`. For the complete Docker route, run `make build`. Rebuild changed native sources even when old outputs exist. Report separately any unavailable compilation, conversion, packaging or runtime checks.

Use outputs from the route just completed:

| Item | Local builds | `make build` export |
| --- | --- | --- |
| Distributable JAR | `java-plugin/build/libs/listener-plugin-template-0.0.1.jar` | `build/listener-plugin-template-0.0.1.jar` |
| Windows bytes for JAR entry `listener.shellcode` | `java-plugin/src/main/resources/listener.shellcode` | `build/listener-execunit-template.shellcode` |
| Linux bytes for JAR entry `listener-linux.native64_so` | `exec-code/linux/build/listener-linux.native64_so` | `build/listener-linux.native64_so` |

Save the following as a temporary Python script in the plugin root and run `python <script>.py` (or `python3`). Set `route` to the route actually used and `uses_jackson` to whether the above dependency was added. Adjust version/archive paths if changed, and `export_dir` if Make used a custom `BUILD_DIR`. The expected parser classes are specific to the Jackson recipe; replace them with the corresponding classes when using another parser.

```python
from pathlib import Path
from zipfile import ZipFile

root = Path.cwd()
route = "local"  # "docker" after make build
uses_jackson = True
export_dir = root / "build"
archive_name = "listener-plugin-template-0.0.1.jar"
service = "META-INF/services/com.shelldot.tuoni.plugin.sdk.listener.ListenerPlugin"
if route == "local":
    archive = root / "java-plugin/build/libs" / archive_name
    artifacts = {
        "listener.shellcode": root / "java-plugin/src/main/resources/listener.shellcode",
        "listener-linux.native64_so": root / "exec-code/linux/build/listener-linux.native64_so",
    }
elif route == "docker":
    archive = export_dir / archive_name
    artifacts = {
        "listener.shellcode": export_dir / "listener-execunit-template.shellcode",
        "listener-linux.native64_so": export_dir / "listener-linux.native64_so",
    }
else:
    raise ValueError("route must be local or docker")

with ZipFile(archive) as jar:
    names = set(jar.namelist())
    for entry, source in artifacts.items():
        fresh_bytes = source.read_bytes()
        assert fresh_bytes and jar.read(entry) == fresh_bytes, entry
    providers = jar.read(service).decode("utf-8").splitlines()
    provider = (root / "java-plugin/src/main/resources" / service).read_text().strip()
    assert provider in providers, service
    assert provider.replace(".", "/") + ".class" in names, provider
    manifest = jar.read("META-INF/MANIFEST.MF")
    for attribute in (b"Plugin-Id:", b"Plugin-Version:", b"Plugin-Name:"):
        assert attribute in manifest, attribute
    assert not any(name.startswith("com/shelldot/tuoni/plugin/sdk/") for name in names)
    if uses_jackson:
        for name in (
            "tools/jackson/databind/json/JsonMapper.class",
            "tools/jackson/core/JsonParser.class",
            "com/fasterxml/jackson/annotation/JsonProperty.class",
        ):
            assert name in names, name
print("Archive resources, provider, manifest and dependencies verified:", archive)
```

Compare only with fresh outputs from the same build; matching an old resource proves no freshness. Archive checks complement execution tests: verify the actual configuration/output path with the SDK or a focused harness. A packaging check using deliberately supplied fixture bytes checks archive wiring only; never report those fixtures as runnable exec-units.
