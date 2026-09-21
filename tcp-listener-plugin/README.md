# Tuoni Example TCP Listener Plugin

A reference implementation of a [Tuoni](https://docs.shelldot.com) **listener plugin** that uses
plain TCP as its C2 transport. It is intended as a starting point and learning resource for anyone
building their own listener plugin — fork it, rename it, swap the transport, and you have a new
plugin.

---

## What's in the box

This example contains **two cooperating projects**:

| Project | Language | Role |
|---|---|---|
| `java-plugin/` | Java 21 / Gradle | Server-side plugin that loads inside the Tuoni server. Opens a TCP `ServerSocket`, accepts implant connections, and bridges them into the Tuoni agent runtime. |
| `exec-code/` | C# / .NET Framework 4.6.2 | Client-side "exec unit" that runs **inside the implant process** on the target. Talks to the Tuoni agent over a local **named pipe** and forwards traffic to the listener over **TCP**. |

`exec-code/exec-unit-utils/` is a shared MSBuild project provided by Tuoni — leave it
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

The Java plugin produces a **Donut-converted shellcode** of the .NET exec unit, embedded as a
classpath resource. When Tuoni asks the plugin to generate a payload, the plugin patches the
shellcode with a per-payload pipe name and hands it back; Tuoni does the rest (delivery, injection,
running it inside an implant).

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

The build has **two halves and one ordering rule**: the .NET exec unit must be built first,
because the Gradle build embeds the resulting `.shellcode` file into the plugin JAR.

### 1. Build the .NET exec unit

You need:
- MSBuild (Visual Studio Build Tools, .NET Framework 4.6.2 targeting pack)
- [`donut.exe`](https://github.com/TheWover/donut) on disk at `exec-code/donut.exe`
  (the `.csproj` post-build event invokes it to convert the built `.exe` into position-independent
  shellcode)

```sh
msbuild exec-code/tcp-listener.slnx /p:Configuration=Release
```

Output: `exec-code/tcp-listener/bin/Release/tcp-listener.shellcode`.

### 2. Build the Java plugin

You need an installed JDK 21 or newer.

```sh
cd java-plugin
./gradlew shadowJar
```

Output: `java-plugin/build/libs/tuoni-example-plugin-tcp-listener-0.0.1.jar` — a single fat
jar containing the plugin code, its runtime dependencies, and the embedded shellcode at
`shellcodes/tcp-listener.shellcode`.

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
- When the Java plugin generates a payload, `TcpListener#generateShellCode` searches the
  shellcode bytes for that exact UTF-16LE sequence and overwrites it in place with the
  per-payload pipe name supplied by Tuoni.

Both sides therefore must declare the **exact same literal**, and the literal must survive into
the compiled binary as a contiguous UTF-16LE string. If you change one side, change the other,
and keep the byte length identical (the patch is in-place, not a resize).

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
└── exec-code/                        .NET exec unit (target-side)
    ├── exec-unit-utils/              **Untouched — provided by Tuoni**
    └── tcp-listener/
        ├── Program.cs                Pipe ↔ TCP bridge
        ├── tcp-listener.csproj
        └── properties/AssemblyInfo.cs
```
