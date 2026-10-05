# Managed utility provenance

`CommunicationNamedPipes`, `CommunicationNamedPipesListener`, and `TLV` retain the
reference helper APIs and wire format used by `listeners_default`. Local
defensive changes bound IPC frame allocation, require complete frames, limit
nested TLV decoding, contain reader/callback exceptions, and release the pipe
and reader even after failed startup or EOF. Windows pipe I/O is cancelled before
close, and the reader is joined. Pending response waiters are woken
on disconnect; each request releases its own wait handle, including failed send
and fast-response paths. Unsolicited responses are discarded.

Startup frame reads have a finite deadline: the positive connection timeout is
also the startup-read timeout, or 10 seconds when a nonpositive timeout was
requested. Timeout cancels/closes only the owned pipe and returns startup failure.
The one-shot timer is stopped and all queued/running callbacks are drained before
starting a reader or returning, including failed-read and validation paths.

The managed TCP entrypoint now owns one pipe connection and one sender thread per
invocation. Pipe loss signals shutdown, closes the active socket, releases pending
requests, and joins the sender before return. Invalid startup configuration also
returns through this cleanup path. These source changes have not been compiled or
run against the host. Full Docker builds and managed DLL lifecycle verification
remain required.
