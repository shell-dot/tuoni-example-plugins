# Listener plugin skeleton

Start with the [shared setup and build instructions](../README.md). This folder
contains one listener plugin and one C# execunit entry point.

| File under `java-plugin/src/main/java/com/example/tuoni/listener/` | Purpose |
| --- | --- |
| `TemplateListenerPlugin.java` | Plugin initialization, configuration validation, and listener factory |
| `TemplateListener.java` | SDK listener lifecycle, reconfiguration, compatibility, and serialization hooks |
| `TemplateConfigurationSchema.java` | Empty configuration schema to customize |

`exec-code/Program.cs` contains initialization, a cancellable idle wait, and
cleanup. The wait blocks without polling; Ctrl+C signals cancellation when running
as a console application. Initialization throws `NotImplementedException`, so the
current program prints that error and exits with code 1 before reaching the wait.

`exec-code/exec-unit-utils/` contains minimal **API stubs** for `TLV`,
`CommunicationNamedPipes`, and `CommunicationNamedPipesListener`. The project
compiles them directly, so they appear in the solution without a shared project.
These are a subset of the example utility APIs, not copies of their implementations.
Encoding, decoding, connection, callback registration, and data exchange are
unimplemented. The entry point does not call these transport stubs.

The Java class implements the same `ShellcodeListener` interface as the listener
example and advertises Windows x86 and x64 payload types. `generateShellCode`
loads `/listener.shellcode` from the JAR, replaces
every UTF-16LE `QQQWWWEEE` pipe-name placeholder with the SDK pipe name, and returns
it with named-pipe IPC and an empty configuration buffer. The new name must have
the same encoded length as the placeholder. Build the C# Release project first so
its post-build step creates `java-plugin/src/main/resources/listener.shellcode`.
Startup, reconfiguration, and updated configuration serialization remain TODO hooks;
stop and delete only update local status.

Open [exec-code/listener-execunit.sln](exec-code/listener-execunit.sln) in Visual Studio,
or build the C# skeleton from this folder:

```powershell
msbuild exec-code/listener-execunit.sln /p:Configuration=Release
```

Output: `exec-code/bin/Release/listener-execunit-template.exe`.
Java output: `java-plugin/build/libs/listener-plugin-template-0.0.1.jar`.
