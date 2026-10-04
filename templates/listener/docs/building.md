# Building and checking the listener plugin

Run commands from the plugin root containing `java-plugin/` and `exec-code/`. Use the actual renamed paths in a generated plugin. Preserve its SDK version, Java target, native ABI, and existing build setup unless the requested change requires updating them.

The [idle source default](../README.md#default-behavior) still requires native compilation, Windows shellcode conversion, and Java packaging before a generated plugin can be loaded. No prebuilt execution resources ship with the template. Its Java code needs no private parser dependency. Keep traffic TODO markers when building an idle scaffold; parser/shading recipes below apply only if dependencies are added. A documentation-only update does not change build inputs.

## Required build checkpoints

Unless the user explicitly requests otherwise, build **the exec-units and the packaged Java plugin in Docker**. Use local build tools only when the user explicitly requests a non-Docker route; missing or unusable Docker does not authorize an automatic fallback. Apply this to complete implementations and focused configuration, logic, or output changes. Keep every existing in-scope platform in the build; lack of a compiler does not remove it from scope.

- Build after a substantial, coherent implementation step: a configuration/codec handoff, major behavior or lifecycle change, transport/output change, or source-list/build/dependency change. Combine closely related edits into one checkpoint; do not build after every small edit.
- After the final code/build-input change, actually execute `make build` from the selected/generated plugin root and wait for it to finish. This is required for each configuration, implementation, logic, and output task, even a Java-only change, and for creation requests that include behavior. It runs the complete Docker pipeline: Windows compilation and shellcode conversion, Linux compilation, Java compilation and dependency/resource packaging, then artifact export. A successful full build already executed during this task counts only when every final build input is unchanged.
- The gate passes only when the complete command exits successfully and the current exported EXE, shellcode, Linux library and distributable JAR are verified as described under [Package and verify](#package-and-verify), including native-byte equality inside the JAR. Record the command, working directory, exit status and artifact paths. Docker readiness checks, a proposed command, `compileJava`, `make build-dotnet`, `make build-linux`, or historical artifacts alone do not establish a full build. A successful build establishes compilation/packaging, not runtime behavior.
- Before reporting the plugin runnable, also pass the [isolated exported-JAR initialization test](java-verification.md#isolated-initialization-smoke-test). Record this Java runtime result separately from the full Docker build, archive checks, and native failure/unload tests; each establishes different behavior.
- Address source/build errors at the checkpoint and rerun the complete Docker build before declaring this gate passed. Where an environmental blocker prevents a phase, continue independent checks and report the phase as unavailable; do not substitute stale artifacts or call the package current.
- If the user explicitly skips builds or narrows platform coverage, honor that instruction and record the skipped checks and artifact freshness. Documentation-only changes need documentation validation, not regenerated binaries.

## Check Docker before building

Use the complete Docker route, `make build`, unless the user explicitly requests another route. First check Docker availability with `Get-Command docker` in PowerShell or `command -v docker` in Linux/WSL; if it is not found, check any known installation location before concluding it is absent. If Docker is not installed, inform the user that Docker is required for these builds and that compilation/packaging could not run. Do not silently run host compilers or Gradle instead.

A Docker executable alone is insufficient: `docker version` must reach the daemon, the daemon must support Linux containers, and the Make recipe needs a Linux/WSL shell with GNU Make and Unix utilities. Run the checks below in that same environment. Report an unreachable daemon, unavailable Linux-container support, missing Make/shell tools, or blocked image/dependency downloads as the specific blocker. Continue independent work and record which build phases remain unverified.

The Makefile checks access through `scripts/docker/run-docker.sh`. A local Docker socket permission denial automatically selects `sudo` while preserving the socket and BuildKit setting; authentication may be required. Do not call a permission-only failure an unavailable Docker installation before trying this route. Rootless or otherwise accessible Docker runs directly. Missing Docker, unavailable daemons and remote failures do not trigger elevation. An explicit `DOCKER=...` override bypasses detection. Help, clean and dry runs do not probe Docker.

The local-tool rows and local recipes below apply only when the user explicitly requested a non-Docker build. Read-only SDK inspection and archive verification may use available host tools; they are not compilation or packaging.

| Route | Required tools and checks | Compatibility |
| --- | --- | --- |
| Docker (default) | In Linux/WSL, `make --version`, `docker version`, and `docker info --format '{{.OSType}}'` returning `linux` | Use GNU Make, a Linux/WSL shell, and standard Unix utilities. The recipes do not run directly in PowerShell/CMD. Docker must be accessible from that shell. |
| Java locally (explicit user override) | `java -version`, `javac -version`, and the checked-in Gradle wrapper | JDK 21+; `options.release = 21` in `java-plugin/build.gradle.kts`. Set `JAVA_HOME` to the selected JDK if necessary. The first wrapper/dependency download needs network access; use `--offline` only when cached. |
| Windows locally (explicit user override) | In Developer PowerShell, `Get-Command msbuild` or `Get-Command dotnet`; use the .NET Framework 4.6.2 targeting pack | The `.csproj` targets .NET Framework 4.6.2. This does not imply support for every modern C# feature or .NET API. Check the compiler used by the selected MSBuild; keep syntax compatible with the Docker Mono compiler too. |
| Linux locally (explicit user override) | In Linux/WSL, `command -v g++` and `g++ --version` | `exec-code/linux/build_linux.sh` uses `-std=c++11`; do not introduce C++14/17 APIs such as `std::make_unique` or `std::optional` without deliberately updating the supported toolchain. The library must remain Linux x64 compatible. |
| Archive checks | `python --version` or `python3 --version` | Python 3; the check below uses only its standard library. |

For an explicitly requested local route, a missing executable on `PATH` is a tool-discovery issue: try the installed JDK's `bin/` tools or Visual Studio Developer PowerShell before declaring that route unavailable. Do not change source code or remove required resources just to bypass an unavailable compiler.

Distinguish an unavailable environment from a compiler, dependency-declaration, or packaging error in the project. Fix project errors and rerun the selected route (Docker by default); switching to a more permissive host compiler does not establish that the Docker build works. An environmental failure must be reported and does not change the build route without an explicit user instruction. Record the actual checks and blocker rather than assuming tools are absent or silently dropping a phase.

## Java dependencies and compilation

The SDK exposes `JsonConfiguration.toJSON()` but supplies no JSON parser. Keep the SDK and any used host-delegated `org.slf4j` / `org.pf4j` API contracts as `compileOnly`; do not package duplicate host API classes. Bundle all plugin-owned runtime libraries **and their complete required transitive dependencies** in the distributable JAR, including JSON parser core and annotation modules.

The reviewed server loader delegates `java.*` to the system loader and the SDK, `org.slf4j.*`, and `org.pf4j.*` to its parent. Other names are loaded from the plugin; its fallback accepts bootstrap-loaded classes only. A library being present in the server or Gradle test classpath does not make it available to this plugin. In particular, do not rely on server Jackson or treat a development-classpath success as packaged-plugin initialization evidence. Follow [Java artifact verification](java-verification.md) for the exact dependency boundary and startup test.

Shadow's default `shadowJar` merges `runtimeClasspath`, including `implementation` and `runtimeOnly` dependencies. Keep required parser dependencies there and retain their transitives; overriding the task's configurations or excluding modules requires inspecting the resulting archive. Dependencies declared in Shadow's separate `shadow(...)` configuration remain external and are not bundled. See [Shadow dependency configuration](https://gradleup.com/shadow/configuration/dependencies/) and [unbundled runtime dependencies](https://gradleup.com/shadow/configuration/#configuring-the-runtime-classpath). Do not use blind `minimize()` or package filters: reflection, service loading, static initialization, and exception types need runtime classes that a compile-only check can miss.

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

Jackson 3 core/databind use `tools.jackson.core.*` and `tools.jackson.databind.*`, including `tools.jackson.core.JacksonException` and `tools.jackson.databind.json.JsonMapper`; its annotations remain in `com.fasterxml.jackson.annotation.*`. Do not copy Jackson 2 core/databind imports or drop the annotations dependency. Verify the exported JAR contains `tools/jackson/core/JacksonException.class`: `NoClassDefFoundError: tools/jackson/core/JacksonException` is a runtime class-loading failure even when compilation succeeded. This example declares the dependency directly because the template has no `libs.jackson.databind` version-catalog alias. Keep the unclassified JAR as the distributable and the `-shallow.jar` as the dependency-free artifact. With the default project name/version, the distributable remains `listener-plugin-template-0.0.1.jar`.

If its name or version changes, update all of these together:

- `java-plugin/settings.gradle.kts`: `rootProject.name`; `java-plugin/build.gradle.kts`: `version` and any archive-name overrides.
- `Makefile`: `JAR_NAME`.
- `scripts/docker/Dockerfile`: the `artifacts` stage's JAR `COPY` source and destination.
- Documentation and verification scripts containing the full archive filename.

Preserve `META-INF/services/com.shelldot.tuoni.plugin.sdk.listener.ListenerPlugin`. Adding `implementation` alone does not bundle dependencies in the plain Java JAR. Confirm the Docker `artifacts` stage copies the shaded distributable produced by `shadowJar`, not the dependency-free `-shallow.jar`, an old archive, or an unintended plain `jar` output. Inspect the exact file exported to `build/`; a correct local shaded JAR does not verify a different Docker export.

By default, compile and package Java through `make build` in Docker together with the native resources. The following direct Gradle commands are only for an explicitly requested local build.

### Local Java compilation (explicit user override only)

In PowerShell:

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

By default, use `make build` to compile both native implementations and package Java inside Docker. The Make targets below have different results; run them in the Linux/WSL shell described above:

| Command | Result |
| --- | --- |
| `make build-linux` | Builds Linux in Docker and writes `exec-code/linux/build/listener-linux.native64_so` plus a copy under `build/`; it does not build Windows or package Java. |
| `make build-dotnet` | Exports only `build/listener-execunit-template.exe`; it does not generate shellcode or a JAR. |
| `make build` | Builds both exec-units, converts Windows shellcode, and packages Java inside Docker; exports the JAR, EXE, shellcode and Linux library under `build/`. It does not refresh the local Gradle output or local native-resource paths. |

### Local native compilation (explicit user override only)

Use these commands only when the user explicitly requested a non-Docker build. On Windows, use the solution so `$(SolutionDir)` is set for its post-build event:

```powershell
msbuild exec-code/win/listener-execunit.sln /t:Rebuild /p:Configuration=Release
```

`dotnet msbuild` with the same arguments is an alternative when the required targeting pack is installed. The post-build event in `exec-code/win/listener-execunit.csproj` converts `exec-code/win/bin/Release/listener-execunit-template.exe` into `listener-execunit-template.shellcode` beside the EXE and copies it to `java-plugin/src/main/resources/listener.shellcode`. The template contains `exec-code/win/donut.exe` for this step. A build using `/p:PostBuildEvent=` verifies C# compilation only and does not refresh the resource.

In Linux/WSL with g++, run:

```sh
bash exec-code/linux/build_linux.sh
```

This produces `exec-code/linux/build/listener-linux.native64_so`. Add new `.cpp` translation units to the compiler command in that script; add new C# files as `<Compile Include="..." />` entries in the `.csproj`. For an explicitly requested local Linux build on Windows, use Linux/WSL; a Windows compiler's output is not a Linux library.

## Package and verify

By default, run `make build` to compile and package everything inside Docker. Only when the user explicitly requested a local build, rebuild both native resources first, then run `bash java-plugin/gradlew -p java-plugin clean build` or `.\java-plugin\gradlew.bat -p java-plugin clean build`. Rebuild changed native sources even when old outputs exist. A successful package must include the fresh resources for every in-scope platform. Report separately any unavailable compilation, conversion, packaging or runtime checks.

Use outputs from the route just completed:

| Item | Local builds (explicit user override) | `make build` export (default) |
| --- | --- | --- |
| Distributable JAR | `java-plugin/build/libs/listener-plugin-template-0.0.1.jar` | `build/listener-plugin-template-0.0.1.jar` |
| Windows bytes for JAR entry `listener.shellcode` | `java-plugin/src/main/resources/listener.shellcode` | `build/listener-execunit-template.shellcode` |
| Linux bytes for JAR entry `listener-linux.native64_so` | `exec-code/linux/build/listener-linux.native64_so` | `build/listener-linux.native64_so` |

First run the supplied archive verifier against the **actual exported distributable** (adjust its name/version and build directory for this plugin):

```sh
python scripts/verify_java_artifact.py build/listener-plugin-template-0.0.1.jar --kind listener
```

Add `--jackson3` when using the Jackson recipe above. That check includes `tools.jackson.core.JacksonException`, parser/databind, and annotation sentinels; it does not prove every possible runtime dependency is present. Add repeatable `--require-class <fully.qualified.ClassName>` arguments for other plugin-owned runtime classes. For an explicitly requested local build, pass the local distributable path from the table. This standard-library Python archive inspection is not a build and does not replace the initialization smoke test below.

Also compare the packaged native bytes with the fresh artifacts from the same build. Save the following as a temporary Python script in the plugin root and run `python <script>.py` (or `python3`). Keep `route = "docker"` for the default build; set it to `"local"` only after an explicitly requested local build. Adjust version/archive paths if changed, and `export_dir` if Make used a custom `BUILD_DIR`. The source descriptor comparison retains the generated plugin's actual provider names and ignores service-file comments and blank lines.

```python
from pathlib import Path
from zipfile import ZipFile

root = Path.cwd()
route = "docker"  # "local" only after an explicitly requested local build
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

def service_providers(contents):
    return {
        provider
        for line in contents.splitlines()
        if (provider := line.split("#", 1)[0].strip())
    }

with ZipFile(archive) as jar:
    for entry, source in artifacts.items():
        fresh_bytes = source.read_bytes()
        assert fresh_bytes and jar.read(entry) == fresh_bytes, entry
    providers = service_providers(jar.read(service).decode("utf-8"))
    source_providers = service_providers(
        (root / "java-plugin/src/main/resources" / service).read_text(encoding="utf-8")
    )
    assert source_providers and providers == source_providers, service
print("Fresh native resources and source service providers verified:", archive)
```

Compare only with fresh outputs from the same build; matching an old resource proves no freshness. A packaging check using deliberately supplied fixture bytes checks archive wiring only; never report those fixtures as runnable exec-units.

Then run the [isolated initialization smoke test](java-verification.md#isolated-initialization-smoke-test) using that exact exported JAR and the real loader policy. Load the listener service provider from that archive, exercise its schemas/examples, then call `init` and any global-command-template hooks used by server startup with suitable SDK contexts. Plugin-private dependencies must resolve from the exported JAR, not loose build classes, Gradle's runtime classpath, the server's unrelated libraries, or sibling JARs added to hide missing classes. Record the archive path/hash and actual entrypoints exercised. A `NoClassDefFoundError`, linkage error, or initializer failure fails this gate: fix the cause in Java code, dependency packaging or artifact selection, rerun the full Docker build, and repeat archive and initialization checks. If the required SDK contexts/compatible loader cannot be supplied, report initialization as unverified; archive class presence alone cannot pass it.

In the final report and project context, give the chosen route, commands and outcomes for native compilation, shellcode conversion, Java compilation, JAR packaging, exported-archive dependency checks, resource comparison, isolated Java initialization, and native runtime checks. Include the distributable path when produced; distinguish passed, failed, unavailable, and explicitly skipped phases. A build verifies compilation and packaging, not Java/native payload agreement or safe unloading.
