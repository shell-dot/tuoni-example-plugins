# Listener native implementation map

Read this when implementing or extending the native runtime. Paths are relative to the plugin root; use the renamed paths in the generated copy. Reuse existing runtime/transport classes instead of introducing duplicate owners. The [IPC reference](execunit-ipc.md) distinguishes the local-agent pipe from the transport to Java.

## Reusing existing implementations

The [existing plugin map](existing-plugins.md) identifies reference helpers and their native/Java peers. Trace `.projitems` / `.vcxitems` imports and POSIX forwarding includes before choosing a source to edit. An EXE/DLL/shellcode wrapper may only delegate to shared logic; a platform `Main.cpp` may include the canonical POSIX implementation. Include shared sources exactly once and update explicit build manifests when adding files.

Adapt helper namespaces, method casing, callbacks, and ownership to this template. Existing managed helpers can use `load` / `getFullBuffer`, while template methods are `Load` / `GetFullBuffer`. Compare implementations before transplanting them; newer bounded helpers and older compatibility paths coexist. Keep these helpers responsible for the native host IPC protocol. Decode plugin configuration and application payloads separately using the format chosen for the task.

## Windows files and methods

| File | Place to implement or extend |
| --- | --- |
| `exec-code/win/Program.cs` | `Main` owns runtime/cancellation state; `Initialize` connects and parses configuration; `WaitForStop` keeps the runtime alive while its transport works; `Cleanup` ends sessions and workers. |
| `exec-code/win/exec-unit-utils/CommunicationNamedPipes.cs` | `Connect` opens the agent pipe and reads initial configuration. Add shared full-frame read/write helpers and reader ownership here; implement safe `Close`/`Dispose`. |
| `exec-code/win/exec-unit-utils/TLV.cs` | `Load` and `GetFullBuffer` decode/encode bounded host IPC envelopes. This helper does not choose the plugin configuration or application payload format. |
| `exec-code/win/exec-unit-utils/CommunicationNamedPipesListener.cs` | Retain/register the constructor callback and `SetCallback`; implement `GetMetadata`, `GetDataToSend`, and `NewDataFromC2`, including sequence-correlated responses and timeout/disconnect handling. |
| `exec-code/win/listener-execunit.csproj` | Add new sources as explicit `<Compile Include="RelativePath.cs" />` entries; new files are not automatically compiled. |

The `using (var pipe = ...)` currently inside `Initialize` ends before the listener loop starts. Move ownership to `Main` or the existing runtime object so the connection survives until shutdown. Preserve `QQQWWWEEE` for Java's shellcode patching.

When restructuring `Main`:

1. Create cancellation/runtime state and register the actual callbacks before starting the pipe reader. Call `Connect`, validate the returned configuration, then initialize the requested transport to Java.
2. Keep both connections alive for their required lifetimes. The pipe reader dispatches local-agent messages; the application transport sends metadata/requests and receives commands from Java. Use a single reader per connection and serialize its writes.
3. Connect transport/pipe disconnects and the chosen retry policy to cancellation. `Console.CancelKeyPress` can remain a console convenience; a native host needs a real disconnect/cancellation path. Replace the placeholder `WaitForStop` with ownership of, or a wait on, those running workers.
4. Replace `catch (NotImplementedException)` with handling for actual configuration, I/O, and transport failures. The listener helper has no command `sendError`/terminal-message API. Use an established application error message when available, then apply the listener's retry/shutdown behavior; do not invent command completion messages.
5. In `finally`, cancel, close resources that unblock reads/waiters, wait for owned workers, and dispose. Cleanup must work after partial initialization and repeated calls. A reader callback should signal shutdown rather than wait for itself to terminate.

Custom output belongs in the application transport encoder and Java decoder. If no separate native transport class exists, keep that code in `Program.cs` initially or introduce a clearly owned helper and include it in the project. Do not put arbitrary Java telemetry in `NewDataFromC2`, which sends opaque server data to the local agent.

## Linux files and methods

| File | Place to implement or extend |
| --- | --- |
| `exec-code/linux/listener/Main.cpp` | Implement exported `run(char*, char*)`: configure callbacks, call `connect`, parse configuration, run the requested application transport, and retain ownership until shutdown. |
| `exec-code/linux/common/CommunicationNamedPipes.h` and `.cpp` | `connect`, `getData`, and `putData` handle framed I/O; `setCallback`/`listenForMessages` dispatch inbound messages; `getMetadata`, `getDataToSend`, `waitForResponseData`, and `newDataFromC2` implement agent exchanges; `close` unblocks and ends owned work. |
| `exec-code/linux/common/TLV.h` and `.cpp` | Preserve the host IPC envelope codec and repair bounds validation where required; plugin payload decoders stay separate. |
| `exec-code/linux/build_linux.sh` | Include any new transport/parser translation units in this exec-unit's compiler invocation; preserve the `run` export and artifact name. |

Keep `run` alive while callbacks/workers can access its pipe and runtime state. Review connection failure, full I/O, bounded lengths, and waiter cancellation in the helper; a valid empty configuration must not be mistaken for connection failure. Catch operation/callback exceptions inside the native runtime. Do not let a C++ exception escape the C export, or wait for the current reader thread from its own callback. Mirror Windows behavior for disconnection, reconnection if supported, and shutdown, and follow the [build guide](building.md) to rebuild resources.
