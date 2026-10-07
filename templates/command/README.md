# Command plugin skeleton

Start with the [shared setup and build instructions](../README.md). This folder
contains one command template, a C# Windows entry point, and C++ native entry points for Windows x86/x64 and Linux x64.

| File under `java-plugin/src/main/java/com/example/tuoni/command/` | Purpose |
| --- | --- |
| `TemplateCommandPlugin.java` | Plugin initialization and command template registration |
| `TemplateCommandTemplate.java` | Name, description, schema, compatibility, validation, and factory |
| `TemplateCommand.java` | SDK command serialization, result, update, and cleanup hooks |
| `TemplateConfigurationSchema.java` | Empty configuration schema to customize |

To implement the entire command from a prompt, use `$command-implement` in Codex
or `/command-implement` in Claude Code. The [implementation skill](.agents/skills/command-implement/SKILL.md)
coordinates configuration, logic, and output through builds, verification, and
project-context updates. It is included in this folder and in generated plugins.

To add configuration fields across Java and the Windows/Linux exec-units, use
`$command-conf` in Codex or `/command-conf` in Claude Code. The skill is included
in this folder and in plugins created from this template.

To implement command behavior with minimal result output, use `$command-logic`
in Codex or `/command-logic` in Claude Code.

To change what users see or receive from a command, use `$command-output` in
Codex or `/command-output` in Claude Code.

The plugin-root [AGENTS.md](AGENTS.md) stores the current implementation context; [CLAUDE.md](CLAUDE.md) directs Claude to that shared context. Each template skill reads and updates it so later tasks retain the plugin's decisions, contracts, checks, and remaining work.

The following guides are copied into generated plugins:

| Task | Guide |
| --- | --- |
| Understand every exec-unit family, format, and current default | [Exec-unit overview](docs/execunit-overview.md) |
| Limit requested support to selected OSs, architectures, or formats | [Support scope and coverage](docs/support-scope.md) |
| Implement a complete command with only the needed features | [Implementation recipe and worked trace](docs/implementation-recipes.md) |
| Adapt an existing Java/native command pair | [Existing plugin patterns](docs/existing-plugins.md) |
| Maintain context for later commands and skills | [Context maintenance](docs/project-context.md) |
| Add configuration and validate its payload encoding | [Configuration walkthrough](docs/configuration.md) |
| Extend native behavior and preserve IPC ownership | [Native runtime](docs/native-runtime.md) |
| Keep one checked terminal success/failure report | [Command completion](docs/command-completion.md) |
| Check message IDs, framing, updates, and stop handling | [IPC reference](docs/execunit-ipc.md) |
| Parse and format complete or streaming results | [Output examples](docs/output.md) |
| Add dependencies, build, and verify the JAR | [Build guide](docs/building.md) |
| Check the exported JAR and isolated Java initialization | [Java verification](docs/java-verification.md) |
| Compare real encoders, decoders, and IPC framing | [Payload verification](docs/payload-verification.md) |

## Default behavior

The default command accepts this configuration:

```json
{}
```

Validation accepts JSON whitespace around the empty object, including multipart
configuration with no uploaded files. Other fields, values, malformed JSON, and
uploads are rejected. The `default` example is `{}`. Java serializes this input as
zero native payload bytes, with each buffer's position and limit both zero;
`{}` is not sent as text to the exec-unit.

It connects to the agent, validates an empty configuration payload, sends `DONE`
as UTF-8 result text, and then sends one success completion. Java displays `DONE`
in the `output` text result. The result payload is exactly four bytes (`44 4f 4e 45`), with no newline or terminator. Startup/validation
or result-send errors select failure completion when the reporting channel is usable.
Managed Windows, native Windows, and Linux entrypoints contain ordinary exceptions and release the connection before returning.

## Extend the template

Add managed Windows behavior in `exec-code/win/Program.cs`'s `Execute`, native
Windows behavior in `exec-code/win-native/command/Main.cpp`, and matching Linux
behavior in `exec-code/linux/command/Main.cpp`'s `execute`. Managed Windows retains
`Initialize`, `Complete`, and `Cleanup`; native Windows keeps its terminal report
and scoped pipe in `Main.cpp`; Linux uses scoped pipe cleanup. Add C# sources to
the `.csproj` and native Windows/Linux translation units to their corresponding
`build_windows.sh` / `build_linux.sh` source lists.
The implemented IPC utilities are compiled directly into each exec-unit. Check the
boolean returned by result/error/terminal sends. Completion has one owner, so the
operation hook must not send an additional terminal message.

To add fields, extend `TemplateConfigurationSchema`, Java validation and the shared
`serializeConfiguration()` encoder, then the managed Windows, native Windows, and Linux configuration decoders. To
add text output, send complete UTF-8 payloads with `sendResult`; Java's `parseResult`
already appends them to the `output` text result. Empty final notifications require
no editor changes. Updates are explicitly unsupported until implemented.

The managed/Linux no-op installs no callbacks or background workers. The native
Windows utility has an owned reader; its callbacks record input and cleanup joins
the reader before releasing callback state. Before adding asynchronous behavior,
apply the [native ownership requirements](docs/native-runtime.md), including
replacing the Linux optional detached callback reader with joined work.

The Java class implements `ExecUnitCommand` and `ShellcodeCommand` and accepts
Windows x86/x64 and Linux x64 `SHELLCODE_AGENT` agents. It advertises `SHELLCODE_NATIVE`, `DOTNET_DLL`, and `DOTNET_EXE`
and `NATIVE_LIB` for Windows, plus `NATIVE_LIB` for Linux x64. Linux loads
`/command-linux.native64_so` with the `run` export; the agent supplies FIFO paths,
so no byte patch is needed. Windows shellcode loads `/command.shellcode` from the JAR,
replaces every UTF-16LE `QQQWWWEEE` pipe-name placeholder with the SDK pipe name,
and returns it with named-pipe IPC and an empty configuration buffer. The new name
must have the same encoded length as the placeholder. Build the C# Release project
first so its post-build step creates
`java-plugin/src/main/resources/command.shellcode`. Build the managed formats, both Windows native DLLs, and Linux library before
a direct Java build so Gradle can include all formats.
Configuration validation, factory creation, empty-result handling, and completion
are implemented; developers can start by adding the desired command operation.

Windows managed assemblies are packaged as `command.dotnet_exe` and
`command.dotnet_dll`. They receive the pipe name in `args[0]`; their bytes are not
patched. DLL generation reads `command.dotnet_dll_method`, emitted from the C#
project namespace as `<namespace>.Program::start`. All formats use the same
configuration and behavior. Windows native DLLs are also packaged as `command.native32_dll` and
`command.native64_dll`, exporting `start(const char*)`. See the
[Windows native implementation and verification guide](docs/windows-native.md).

## Build

Skills build with Docker unless the user explicitly requests another route. If Docker
is missing or unusable, inform the user and report the blocked build; do not fall
back to local tools. The local build examples below apply only to an explicitly
requested non-Docker route.

Open [exec-code/win/command-execunit.sln](exec-code/win/command-execunit.sln) in Visual Studio,
or build the C# exec-unit from this folder:

```powershell
msbuild exec-code/win/command-execunit.sln /p:Configuration=Release
```

Output: `exec-code/win/bin/Release/command-execunit-template.exe`.
Java output: `java-plugin/build/libs/command-plugin-template-0.0.1.jar`.

For a direct Linux build, run `bash exec-code/linux/build_linux.sh` on Linux with
`g++`. This writes `exec-code/linux/build/command-linux.native64_so`. To build it
inside Docker and extract it for Gradle, run `make build-linux`.

Use a Linux shell (WSL on Windows), GNU Make, standard Unix file utilities, and
Docker configured for Linux containers. Run `make build` from this folder. The JAR,
managed EXE/DLL, DLL method metadata, legacy shellcode-input EXE, shellcode, and
Windows native DLLs and Linux library are extracted to `build/`. `make build-dotnet` exports the C#
artifacts without shellcode conversion or Java packaging. The Java build runs
`execUnitFormatsCheck` against rebuilt resources; see the [build guide](docs/building.md).

For an explicitly requested local build, additionally run:

```powershell
msbuild exec-code/win/command-execunit.csproj /p:Configuration=Release /p:ExecUnitFormat=dotnet-exe
msbuild exec-code/win/command-execunit.csproj /p:Configuration=Release /p:ExecUnitFormat=dotnet-dll
```

Managed artifacts appear in `bin/Release/dotnet-exe/` and
`bin/Release/dotnet-dll/` under `exec-code/win/`. The default format remains
`shellcode`. Unsupported `ExecUnitFormat` values fail the build.

Use `make build-windows-native` to build and export just the Windows native DLLs.
