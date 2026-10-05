# Tuoni Example TCP Listener Plugin

A reference implementation of a [Tuoni](https://docs.shelldot.com) **listener plugin** that uses
plain TCP as its C2 transport. It is intended as a starting point and learning resource for anyone
building their own listener plugin — fork it, rename it, swap the transport, and you have a new
plugin.

For a minimal listener starting point, use the [listener template](../templates/listener/README.md).
It already accepts `{}`, implements Java lifecycle, and starts native IPC while
idling until host disconnect. Its traffic channel remains TODO; this TCP example
shows an implemented channel to adapt when needed.

---

## What's in the box

This example contains **two cooperating projects**:

| Project | Language | Role |
|---|---|---|
| `java-plugin/` | Java 21 / Gradle | Server-side plugin that loads inside the Tuoni server. Opens a TCP `ServerSocket`, accepts implant connections, and bridges them into the Tuoni agent runtime. |
| `exec-code/` | C# / .NET Framework 4.6.2 and Linux C++ | Client-side execunits that run inside the agent process. They talk to the agent over local IPC and forward traffic to the listener over TCP. |

`exec-code/win/exec-unit-utils/` is a shared MSBuild project provided by Tuoni — leave it
alone.

### Architecture at a glance

```
   ┌──────────────────┐         TCP            ┌──────────────────────────┐
   │  Tuoni server    │  <─── framed bytes ──> │  Target machine           │
   │                  │                        │                           │
   │  TcpListener     │                        │  ┌─────────────────────┐  │
   │  (this plugin)   │                        │  │ Implant process     │  │
   │       │          │                        │  │                     │  │
   │       │ Agent    │                        │  │  Tuoni agent        │  │
   │       │ runtime  │                        │  │       │ named pipe  │  │
   │       ▼          │                        │  │       ▼             │  │
   │  Tuoni core      │                        │  │  tcp-listener       │  │
   └──────────────────┘                        │  └─────────────────────┘  │
                                               └──────────────────────────┘
```

The Java plugin embeds shellcode, managed EXE/DLL, and native DLL formats for Windows x86/x64,
and a native shared object for Linux x64. Only shellcode is patched with a pipe name.
Managed assemblies receive the pipe name in `args[0]`; DLL generation reads the
public method name from `tcp-listener.dotnet_dll_method`.
The Linux agent loader supplies FIFO paths to the native `run` entrypoint.
The plugin advertises Windows as `SHELLCODE_NATIVE`, `DOTNET_EXE`, `DOTNET_DLL`, and `NATIVE_LIB`,
and Linux x64 as `NATIVE_LIB` through
the listener exec-unit API.

### Frame protocol

A single message  on the TCP socket is:

```
  ┌──────────────┬───────────────────┬──────────────┬──────────────────┐
  │ metaLen (u32 │  meta bytes       │ dataLen (u32 │  data bytes      │
  │ little-end.) │  (metaLen bytes)  │ little-end.) │  (dataLen bytes) │
  └──────────────┴───────────────────┴──────────────┴──────────────────┘
```
or

```
  ┌──────────────┬──────────────────┐
  │ dataLen (u32 │  data bytes      │
  │ little-end.) │  (dataLen bytes) │
  └──────────────┴──────────────────┘
```

- `meta` is the agent metadata blob produced by the Tuoni SDK.
- `data` is an opaque serialized request/response. `dataLen == 0` is allowed and is used by the
  exec unit's first frame to register the agent.
- Server-to-client frames omit the meta section and carry only `<lenLE><bytes>` (a single command
  payload). See `TcpConnectionHandler#runCommandPusher` and `Program.RunReadLoop` for the
  authoritative encoders.

---

## Building

Run the commands below from `tcp-listener-plugin/`.

`make build` compiles and embeds Windows `.shellcode`, `.dotnet_exe`, `.dotnet_dll`,
DLL entrypoint metadata, Windows `.native32_dll`/`.native64_dll`, and Linux x64
`.native64_so` in Docker. All formats are
exported to `build/` alongside the plugin JAR and legacy shellcode-input `.exe`.
`make build-dotnet` exports the managed artifacts without shellcode conversion
or Java compilation. The Java build runs `execUnitFormatsCheck` against rebuilt
resources to verify platform selection, PE DLL/EXE roles, entrypoints, and bytes;
it does not execute native code or establish host/unload safety.

The following direct-build steps must produce all formats before Java packaging.

### 1. Build the .NET exec unit

You need:
- MSBuild (Visual Studio Build Tools, .NET Framework 4.6.2 targeting pack)
- [`donut.exe`](https://github.com/TheWover/donut) on disk at `exec-code/win/donut.exe`
  (the `.csproj` post-build event invokes it to convert the built `.exe` into position-independent
  shellcode)

```sh
msbuild exec-code/win/tcp-listener.slnx /p:Configuration=Release
msbuild exec-code/win/tcp-listener.slnx /p:Configuration=Release /p:ExecUnitFormat=dotnet-exe
msbuild exec-code/win/tcp-listener.slnx /p:Configuration=Release /p:ExecUnitFormat=dotnet-dll
```

Outputs: `exec-code/win/tcp-listener/bin/Release/tcp-listener.shellcode`,
`dotnet-exe/tcp-listener.dotnet_exe`, and `dotnet-dll/tcp-listener.dotnet_dll`
plus `tcp-listener.dotnet_dll_method` under the same Release directory.
The metadata names `TcpListenerExecUnit.Program::start`.

### 1b. Build the Linux execunit

Run the Ubuntu 18.04 amd64 Docker build target from `tcp-listener-plugin/`:

```sh
make build-linux
```

Output: `exec-code/linux/build/tcp-listener-linux.native64_so` for Gradle and
`build/tcp-listener-linux.native64_so` for direct use. The full `make build`
also exports its JAR and Windows artifacts to `build/`; `BUILD_DIR` overrides that location.

### 2. Build the Java plugin

You need an installed JDK 21 or newer.

```sh
cd java-plugin
sh gradlew shadowJar
```

Output: `java-plugin/build/libs/tuoni-example-plugin-tcp-listener-0.0.1.jar` — a single fat
jar containing the plugin code, its runtime dependencies, the Windows shellcode at
`shellcodes/tcp-listener.shellcode`, managed `.dotnet_exe`/`.dotnet_dll` and
DLL method metadata in the same resource directory, and the Linux execunit at
`shellcodes/tcp-listener-linux.native64_so`.

### 3. Deploy

Drop the shadow jar into your Tuoni server's plugins directory and restart. The plugin advertises
itself with `Plugin-Id = shelldot.listener.examples.tcp` (set in `build.gradle.kts`).

---

## Configuration

The plugin exposes a tiny JSON schema (declared in
`TcpListenerPluginConfiguration.JSON_SCHEMA`):

```json
{
  "connectBackAddress": "0.0.0.0",
  "port": 4444
}
```

`connectBackAddress` is informational (used as the connect-back address baked into generated payloads); `port`
is the actual TCP port the listener binds to. Tuoni's UI renders the schema as a form when an
operator creates a new listener instance.

---

## The `QQQWWWEEE` placeholder — read this before changing it

Both `TcpListener.DEFAULT_PIPE_NAME` (Java) and `Program.DefaultPipeName` (C#) hold the literal
string `"QQQWWWEEE"`. This is **not** a bug or a leftover — it is a deliberate marker.

- In the .NET exec unit it is used as the named-pipe name to connect to.
- In the compiled shellcode it appears verbatim as a UTF-16LE byte sequence.
- When the Java plugin generates a payload, `TcpListener#generateExecUnit` searches the
  shellcode bytes for that exact UTF-16LE sequence and overwrites it in place with the
  per-payload pipe name supplied by Tuoni.

Both sides therefore must declare the **exact same literal**, and the literal must survive into
the compiled binary as a contiguous UTF-16LE string. If you change one side, change the other,
and keep the byte length identical (the patch is in-place, not a resize).

Linux uses the native `run` export and receives two FIFO paths from the agent loader;
its shared object does not contain or require this placeholder.

---

## Customising this template for your own listener

A short checklist for turning this into a brand-new listener plugin:

1. Rename the Gradle root project (`settings.gradle.kts`) and the shadow jar
   (`build.gradle.kts: archiveBaseName`).
2. Change the `Plugin-Id`, `Plugin-Name`, `Plugin-Description`, `Plugin-Provider` manifest
   attributes in `build.gradle.kts`.
3. Rename the Java package under
   `java-plugin/src/main/java/com/shelldot/tuoni/examples/plugin/tcplistener` to your own.
4. Replace the TCP transport in `TcpConnectionHandler` (and the matching client logic in
   `Program.cs`) with your own — HTTP, DNS, SMB, whatever — keeping the framing protocol or
   designing your own.
5. Update `TcpListenerPluginConfiguration` (and its JSON schema) to expose the configuration
   fields your transport needs.
6. Rebuild .NET → rebuild Java → drop the new jar into Tuoni.

---

## Repository layout

```
tcp-listener-plugin/
├── README.md
├── java-plugin/                      Java/Gradle plugin (server-side)
│   ├── build.gradle.kts              shadowJar build, manifest, shellcode embedding
│   ├── settings.gradle.kts
│   └── src/main/java/.../tcplistener
│       ├── TcpListenerPlugin.java            Plugin entry point (init / create)
│       ├── TcpListener.java                  Listener lifecycle (start/stop/reconfigure)
│       ├── TcpConnectionHandler.java         Per-connection read/write loops
│       ├── TcpFrameCodec.java                Length-prefixed framing helpers
│       ├── TcpListenerPluginConfiguration.java   Config record + JSON schema
│       ├── ShellcodeUtil.java                Read/patch the embedded shellcode
│       └── configuration/                    Thin SDK adapters
└── exec-code/                        Agent execunits
    ├── win/
    │   ├── exec-unit-utils/          Shared .NET project
    │   ├── tcp-listener.slnx
    │   └── tcp-listener/             Windows pipe ↔ TCP bridge
    └── linux/
        ├── common/                   FIFO/TLV communication
        ├── tcp-listener/Main.cpp     Linux FIFO ↔ TCP bridge
        └── build_linux.sh
```

The [managed utility notes](exec-code/win/exec-unit-utils/README.md) document local
parser and resource safety fixes. The managed TCP entrypoint now closes its active
socket and joins its sender thread when the host pipe disconnects, including during
a pending connection attempt or response wait. Managed DLL unload safety still
requires a compiled runtime check.

## Windows native libraries

Run `make build-windows-native` to cross-compile Windows x86/x64 DLLs in Docker
using MinGW. Native source lives under `exec-code/win-native/`. Each DLL exports
exactly `start(const char* pipeName)`; Java selects `.native32_dll` or
`.native64_dll` using the agent process architecture and passes the bytes unchanged.
The pipe/configuration and result/TCP protocols match the other formats.
`make build` embeds and exports these DLLs with the Java plugin; the standalone
target also writes them to `exec-code/win-native/build/` for direct Gradle builds.

The native listener uses `CommunicationNamedPipes`, `TLV`, `Conversions`, and
`RaiiHelpers`, copied from the Windows TCP listener in `listeners_default` into
[`exec-unit-utils/`](exec-code/win-native/exec-unit-utils/README.md). Documented
local changes support MinGW headers, bounded I/O, cancellation-aware response
waits, and cleanup that cancels/drains I/O and joins the reader. A separate
sender worker keeps pipe polling from blocking TCP reads. The invocation owns the TCP socket;
registration still sends both metadata/data lengths.
The build's [PE verifier](scripts/verify_windows_native.py) checks architecture,
the sole `start` export, absence of a CLR header and OS-only DLL dependencies.

After building, use Windows Python matching the DLL architecture to run local IPC,
failure/disconnect, repeated invocation and immediate unload checks:

```powershell
python scripts/check_windows_native_runtime.py build/tcp-listener.native64_dll --mode tcp-listener
```

Use a 32-bit Python for `.native32_dll`. The TCP check uses a loopback peer and exercises both traffic directions, including a deferred pipe response. The
[check harness](scripts/check_windows_native_runtime.py) runs each case in a child
process with a watchdog; it does not replace real Tuoni agent integration tests.
