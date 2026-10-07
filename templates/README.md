# Plugin skeleton templates

Copy one of these folders to start a plugin. Each folder is independent and uses the
same Java server plugin / `exec-code` layout as the repository examples.

For a first reading, use the [command exec-unit overview](command/docs/execunit-overview.md)
or [listener exec-unit overview](listener/docs/execunit-overview.md). Each explains
all three source families, their generated formats, and the existing default
lifecycle before the detailed guides. The [payload source overview](payloads/README.md#source-and-current-behavior)
describes a separate, unfinished program template; command/listener skill
workflows do not establish its implementation status.

For requests covering only some OSs, architectures, or exec-unit formats, see
the [command support-scope guide](command/docs/support-scope.md) or
[listener support-scope guide](listener/docs/support-scope.md). Each is copied
with its template and distinguishes support restrictions from task/test limits.

| Folder | Java server plugin | Native starting point |
| --- | --- | --- |
| [command](command/README.md) | Empty configuration, factory, UTF-8 results, and lifecycle | Windows/Linux pipe startup, `DONE`, and success completion |
| [listener](listener/README.md) | Empty configuration, factory, and idle lifecycle | Windows/Linux pipe startup and disconnect waiting; traffic TODO |
| [payloads](payloads/README.md) | Payload registration, template, and output object | Payload program entry point |

The command template is a no-op starting point: Java accepts `{}`, the Windows and
Linux exec-units connect, return `DONE`, and report success without performing an
operation. Java displays that text in the `output` result; the execution hooks
are ready for new code. It supports Windows x86/x64 agents in all four exec-unit formats and Linux x64 native-library agents. Windows uses `SHELLCODE_NATIVE`,
`DOTNET_DLL`, `DOTNET_EXE`, or `NATIVE_LIB` (x86/x64 native DLLs with `start`);
Linux uses a `NATIVE_LIB` with a `run` entry point. Its pipe/FIFO and TLV utilities
are implemented, with checked result and completion sends.

The listener template accepts `{}` and implements Java lifecycle and native
local-agent IPC startup for Windows x86/x64 and Linux x64. Its exec-units remain
idle until host disconnect; the data traffic channel is intentionally TODO in Java
and all exec-unit entrypoints. The payload template retains unimplemented behavior.
Native utilities live under `exec-code/win/exec-unit-utils/`, `exec-code/win-native/exec-unit-utils/`,
and `exec-code/linux/common/`. Windows native entrypoints are built separately from C#.

These native helpers implement the local agent's pipe/FIFO protocol. Java
configuration and result APIs exchange the inner payload bytes, whose format is
defined by the plugin: for example UTF-8 text, JSON, or explicit binary fields.
Java payload code uses standard text/binary APIs or a declared parser dependency;
it does not need the native helper's envelope codec or server-internal classes.

## Customize a copy

1. Copy the entire `command`, `listener`, or `payloads` folder to your own project,
   including `.gitattributes` and the other dotfiles. The attributes keep the
   Gradle wrapper and Docker build files in LF format on Windows checkouts.
2. Rename `com.example.tuoni.*`, the Java classes, and the C# namespace. Update the
   provider class name in `java-plugin/src/main/resources/META-INF/services/` to
   match your renamed plugin class. Keep the service file's SDK interface name.
3. Set your project name in `java-plugin/settings.gradle.kts` and the version,
   group, and `Plugin-*` manifest attributes in `java-plugin/build.gradle.kts`.
4. Rename the C# project, `RootNamespace`, and `AssemblyName` in its `.csproj`,
   and update the project name and path in its `.sln` under `exec-code/win/`.
   Keep the project GUID
   consistent between the two files.
5. Update `scripts/docker/Dockerfile` for the renamed `.csproj`, Linux library,
   and all renamed output files in its build and copy instructions. Update the
   full build, `dotnet-artifacts`, `windows-native-artifacts`, and `linux-artifacts` export stages. In
   `Makefile`, set `JAR_NAME` to the complete Gradle output filename (including
   its version and `.jar` extension)
   and `EXEC_NAME` to the C# `AssemblyName` without `.exe`. Update the Linux output
   name in the Makefile and Gradle resource task. Rename the Windows native source
   directory and `units` entry in `exec-code/win-native/build_windows.sh`, and update
   its x86/x64 DLL names in Docker, Make, Gradle, and Java together; retain `start`
   in `exports.def`. These Makefile variables
   do not change the Dockerfile paths; both files must agree with your project
   settings. Update the project README's build commands and output names too.
6. For commands, extend managed Windows `Execute`, native Windows `start` in
   `exec-code/win-native/command/Main.cpp`, Linux `execute`, and Java
   `parseResult`.
   For listeners, implement the requested channel at the Java/native TODO markers.
   Add configuration fields only when needed: extend `TemplateConfigurationSchema`,
   validation, the shared `serializeConfiguration()` encoder, and all exec-unit decoders.
   Preserve the implemented IPC helpers and cleanup/completion ownership.

The Java builds use SDK **0.15.0**, matching the examples, as a `compileOnly`
dependency. The SDK is supplied by Tuoni at runtime. These skeletons have no
additional runtime dependencies, so the standard Gradle JAR task is sufficient.
If you add runtime libraries, bundle those dependencies in your plugin JAR.

## Build

Use GNU Make from a Linux shell with Docker configured for Linux containers and
standard Unix file utilities. On Windows, run the Make targets from a Linux shell
in WSL with Docker accessible there; PowerShell and CMD cannot run these recipes.
The repository's example help targets additionally require GNU `sed` and `column`.

Run `make build` in an individual template folder or `templates/`.
A command or listener build compiles C#, Windows/Linux C++, and Java inside Docker and
extracts the plugin JAR and both platforms' execunits to that template's `build/`
directory. Run `make build-windows-native` in the command, listener, or `templates/` folder
to build the x86/x64 Windows DLLs. Run `make build-linux` in the same folder
to build and extract Linux libraries for a direct Gradle build. Run
`make build-dotnet` in the same locations to compile and extract only the C#
EXE/DLL formats and DLL entrypoint metadata, without building Java or generating
shellcode. The legacy shellcode-input EXE is also exported. Run `make clean` in
the same location to remove the extracted artifacts. The templates are
skeletons, so the aggregate
`make install` target does not install them.

The default Docker runner checks access when a build runs and automatically uses
`sudo` if the local socket denies permission, including users outside the Docker
group. Sudo may prompt for authentication. Accessible Docker/rootless setups run
directly; missing Docker, unavailable daemons and remote failures are reported.
The runner preserves the selected socket and BuildKit setting.

An explicit `DOCKER=...` override bypasses detection; for example,
`make build DOCKER="sudo env DOCKER_BUILDKIT=1 docker"` forces sudo. Overrides also
work for `build-dotnet`, `build-windows-native`, and `build-linux` and propagate from `templates/`.
Help, clean and dry runs do not probe Docker.

Use `BUILD_DIR="build/custom output"` for another output subdirectory, including
one with spaces. Paths under `build/` are covered by the template's `.gitignore`.
If you choose a directory outside `build/`, add it to `.gitignore` before building.
Reserve it for generated files: `make clean` removes the entire directory,
including outputs from previous versions or project names. Cleanup requires the
resolved output directory to be a subdirectory of the project.

Command/listener skills always use Docker unless the user explicitly requests
another build route. If Docker is missing or unusable, inform the user and report
the blocked build instead of falling back to local tools. The direct build steps
below apply to skills only with that explicit override.

Java requires **JDK 21+**. Each folder includes the repository's Gradle wrapper;
the first build needs network access to obtain Gradle and the SDK dependencies.
Run from the copied folder:

```sh
cd java-plugin
sh gradlew assemble
```

On Windows PowerShell:

```powershell
cd java-plugin
.\gradlew.bat assemble
```

The JAR is written to `java-plugin/build/libs/` and includes plugin manifest
metadata and service registration.
For the command and listener templates, direct Gradle builds require every resource
below. Replace `<kind>` with `command` or `listener`; these are paths inside that
template folder.

| Format | Required input before Gradle |
| --- | --- |
| Windows shellcode | `java-plugin/src/main/resources/<kind>.shellcode` |
| .NET EXE | `exec-code/win/bin/Release/dotnet-exe/<kind>-execunit-template.dotnet_exe` |
| .NET DLL and entrypoint | `exec-code/win/bin/Release/dotnet-dll/<kind>-execunit-template.dotnet_dll` and `.dotnet_dll_method` |
| Windows native x86/x64 | `exec-code/win-native/build/<kind>.native32_dll` and `<kind>.native64_dll` |
| Linux native x64 | `exec-code/linux/build/<kind>-linux.native64_so` |

The default `make build` prepares these resources inside Docker and exports the
packaged JAR. It does not populate the local Gradle input paths. The partial
`make build-windows-native` and `make build-linux` targets populate their local
native input paths; `make build-dotnet` exports managed files under `build/`,
which is a different location from Gradle's managed input paths.

With an explicit local-build override, build the C# solution in Release with its
post-build event to create the shellcode resource. Build the C# project again with
`/p:ExecUnitFormat=dotnet-exe` and `/p:ExecUnitFormat=dotnet-dll`; the imported
`ExecUnitFormats.targets` writes the managed artifacts and DLL method sidecar to
the paths above. See the individual [command](command/README.md) or
[listener](listener/README.md) README for exact MSBuild commands.

Build both Windows native DLLs using `bash exec-code/win-native/build_windows.sh`
with the POSIX-thread MinGW compilers `i686-w64-mingw32-g++-posix` and
`x86_64-w64-mingw32-g++-posix` plus Python 3. Build Linux with
`bash exec-code/linux/build_linux.sh` using a Linux C++11 compiler. The Docker
partial targets above are also available. Refresh every changed artifact before
running Gradle; missing or empty inputs fail `processResources`. The JAR contains
all formats, and `generateExecUnit` chooses by OS, process architecture, and type.
Each template's [build guide](command/docs/building.md) lists its exact names and
freshness/packaging checks; the [listener guide](listener/docs/building.md) covers
the listener outputs.

C# requires **MSBuild** and the **.NET Framework 4.6.2 targeting pack**, matching
the examples. The command and listener templates include a Visual Studio `.sln`
in `exec-code/win/` with
Debug and Release configurations for Any CPU. Open it in Visual Studio, or build
it from a Visual Studio Developer PowerShell using the command in the template's
README. The shellcode-input executable is written to `exec-code/win/bin/Release/`;
managed EXE/DLL variants use the separate format subdirectories listed above.

The command and listener templates contain the working defaults described above,
but no application operation or listener traffic channel. They contain no prebuilt
execution artifacts. The
repository's root Makefile continues to build the full examples; build a template
directly using the commands above.
