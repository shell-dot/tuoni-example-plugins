# Windows listener utilities

These classes come from
`listeners_default/listeners/simple_tcp_listener/execunits/windows/TcpListenerNativeDll`.
[UPSTREAM.json](UPSTREAM.json) records original LF-normalized file hashes and the files with
local changes. The TCP example and listener template carry identical copies.

The native code uses `CommunicationNamedPipes` for startup, metadata, outgoing
requests and incoming data, together with the reference `TLV`, `Conversions`
and `RaiiHelpers`. The build compiles the three utility implementation files
and links them into each DLL.

The following local changes preserve the template's build and unload requirements:

- `CommunicationNamedPipes.h/.cpp`: atomic connection status and an
  `isConnected()` query distinguish valid empty configuration from startup
  failure. A shutdown event cancels and drains overlapped I/O; cleanup joins the
  reader before freeing handles, callbacks or response state. Frame sizes,
  envelope depth/node counts, partial reads and writes are bounded. Response
  waits continue while the pipe is connected and cancel on shutdown.
  Writes check all bytes; response signals are registered before sending.
  The reader accepts an omitted data child on an idle result response, contains
  exceptions and wakes waiting calls on disconnect.
- `TLV.h/.cpp`: explicit standard-library includes and portable packing for
  MinGW. Destructor cleanup detaches sibling links without allocating a temporary
  container; both destruction and `clear()` are explicitly nonthrowing.
- `Conversions.h`: provide the existing `byte` alias explicitly, so builds with
  `WIN32_LEAN_AND_MEAN` do not depend on indirectly included RPC headers.
- `RaiiHelpers.h`: include Winsock before Windows so socket declarations do not
  depend on include order.

The original `TLV.tpp` and `Conversions.cpp` remain unchanged. The owner must stop
and destroy the pipe outside its callbacks,
after application calls finish. The listener template leaves the application
traffic channel unimplemented.

Review these local changes when refreshing the reference files. Source-copy
checks do not establish successful compilation, IPC, or DLL unload behavior.
