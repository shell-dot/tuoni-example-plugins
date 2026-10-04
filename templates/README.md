# Plugin skeleton templates

Copy one of these folders to start a plugin. Each folder is independent and uses the
same Java server plugin / `exec-code` layout as the repository examples.

| Folder | Java server plugin | Native starting point |
| --- | --- | --- |
| [command](command/README.md) | Empty configuration, factory, UTF-8 results, and lifecycle | Windows/Linux pipe startup, `DONE`, and success completion |
| [listener](listener/README.md) | Empty configuration, factory, and idle lifecycle | Windows/Linux pipe startup and disconnect waiting; traffic TODO |
| [payloads](payloads/README.md) | Payload registration, template, and output object | Payload program entry point |

The command template is a no-op starting point: Java accepts `{}`, the Windows and
Linux exec-units connect, return `DONE`, and report success without performing an
operation. Java displays that text in the `output` result; the execution hooks
are ready for new code. It supports Windows x86/x64 shellcode
agents and Linux x64 native-library agents. Windows uses `SHELLCODE_NATIVE`;
Linux uses a `NATIVE_LIB` with a `run` entry point. Its pipe/FIFO and TLV utilities
are implemented, with checked result and completion sends.

The listener template accepts `{}` and implements Java lifecycle and native
local-agent IPC startup for Windows x86/x64 and Linux x64. Its exec-units remain
idle until host disconnect; the data traffic channel is intentionally TODO in Java
and both native entrypoints. The payload template retains unimplemented behavior.
Native utilities live under `exec-code/win/exec-unit-utils/` and `exec-code/linux/common/`.

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
   full build, `dotnet-artifacts`, and `linux-artifacts` export stages. In
   `Makefile`, set `JAR_NAME` to the complete Gradle output filename (including
   its version and `.jar` extension)
   and `EXEC_NAME` to the C# `AssemblyName` without `.exe`. Update the Linux output
   name in the Makefile and Gradle resource task. These Makefile variables
   do not change the Dockerfile paths; both files must agree with your project
   settings. Update the project README's build commands and output names too.
6. For commands, extend the existing `Execute`/`execute` hooks and `parseResult`.
   For listeners, implement the requested channel at the Java/native TODO markers.
   Add configuration fields only when needed: extend `TemplateConfigurationSchema`,
   validation, the shared `serializeConfiguration()` encoder, and both native decoders.
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
A command or listener build compiles C#, Linux C++, and Java inside Docker and
extracts the plugin JAR and both platforms' execunits to that template's `build/`
directory. Run `make build-linux` in the command, listener, or `templates/` folder
to build and extract Linux libraries for a direct Gradle build. Run
`make build-dotnet` in the same locations to compile and extract only the C#
executable, without building Java or generating shellcode. Run `make clean` in
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
work for `build-dotnet` and `build-linux` and propagate from `templates/`.
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
For the command and listener templates, build the C# project in Release first. Its
post-build step places `command.shellcode` or `listener.shellcode` in that plugin's
`java-plugin/src/main/resources/` folder. Build the Linux x64 library into
`exec-code/linux/build/` with `make build-linux` or
`bash exec-code/linux/build_linux.sh` before running Gradle. Gradle includes both
resources in the JAR. Windows `generateShellCode` retains the legacy shellcode
path; `generateExecUnit` selects the resource by platform.

C# requires **MSBuild** and the **.NET Framework 4.6.2 targeting pack**, matching
the examples. The command and listener templates include a Visual Studio `.sln`
in `exec-code/win/` with
Debug and Release configurations for Any CPU. Open it in Visual Studio, or build
it from a Visual Studio Developer PowerShell using the command in the template's
README. Their executable is written to `exec-code/win/bin/Release/`.

The command and listener templates contain the working defaults described above,
but no application operation or listener traffic channel. They contain no prebuilt
execution artifacts. The
repository's root Makefile continues to build the full examples; build a template
directly using the commands above.
