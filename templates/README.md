# Plugin skeleton templates

Copy one of these folders to start a plugin. Each folder is independent and uses the
same Java server plugin / C# `exec-code` layout as the repository examples.

| Folder | Java server plugin | C# skeleton |
| --- | --- | --- |
| [command](command/README.md) | Command registration, template, and command lifecycle | Command execunit entry point |
| [listener](listener/README.md) | Listener registration and lifecycle | Listener execunit entry point |
| [payloads](payloads/README.md) | Payload registration, template, and output object | Payload program entry point |

These are source skeletons with `TODO` markers. Java configuration validation and
most behavior methods deliberately report that they are unimplemented. The command
accepts Windows shellcode agents, and the listener advertises Windows x86 and x64
payload types. Each C#
program prints an unimplemented message and exits with code 1. Its entry point is
scaffolding, not an implementation of the execunit protocol or a payload agent.

The command and listener projects include minimal utility API stubs under
`exec-code/exec-unit-utils/`: `TLV`, `CommunicationNamedPipes`, and the corresponding
command or listener helper. These are partial declarations with unimplemented
encoding and communication methods. Their entry points outline lifecycle hooks;
the listener includes a cancellable idle wait after its initialization hook.

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
   and update the project name and path in its `.sln`. Keep the project GUID
   consistent between the two files.
5. Update `scripts/docker/Dockerfile` for the renamed `.csproj` and all renamed
   output files in its build and copy instructions. Update both the full build
   and the `dotnet-artifacts` export stage. In `Makefile`, set `JAR_NAME` to the
   complete Gradle output filename (including its version and `.jar` extension)
   and `EXEC_NAME` to the C# `AssemblyName` without `.exe`. These Makefile variables
   do not change the Dockerfile paths; both files must agree with your project
   settings. Update the project README's build commands and output names too.
6. Define configuration fields in `TemplateConfigurationSchema`, then implement
   the validation and behavior hooks marked `TODO`.

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
A template build compiles the C# and Java
projects inside Docker and extracts the plugin JAR and .NET artifacts to that
template's `build/` directory. Run `make build-dotnet` in the same locations to
compile and extract only the C# executable, without building Java or generating
shellcode. Run `make clean` in the same location to remove
the extracted artifacts. The templates are skeletons, so the aggregate
`make install` target does not install them.

The Docker command defaults to `docker`. If your setup requires sudo, use
`make build DOCKER="sudo docker"`; the same override works for `build-dotnet` and
is passed through when building from `templates/`.

Use `BUILD_DIR="build/custom output"` for another output subdirectory, including
one with spaces. Paths under `build/` are covered by the template's `.gitignore`.
If you choose a directory outside `build/`, add it to `.gitignore` before building.
Reserve it for generated files: `make clean` removes the entire directory,
including outputs from previous versions or project names. Cleanup requires the
resolved output directory to be a subdirectory of the project.

To build directly without Docker, follow the steps below.

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
`java-plugin/src/main/resources/` folder. The Java build then includes the file
in the JAR. `generateShellCode` reads the packaged resource when called.

C# requires **MSBuild** and the **.NET Framework 4.6.2 targeting pack**, matching
the examples. Each template includes a Visual Studio `.sln` in `exec-code/` with
Debug and Release configurations for Any CPU. Open it in Visual Studio, or build
it from a Visual Studio Developer PowerShell using the command in the template's
README. The executable is written to `exec-code/bin/Release/`.

The templates contain no business logic or prebuilt execution artifacts. The
repository's root Makefile continues to build the full examples; build a template
directly using the commands above.
