# Managed utility provenance

`CommunicationNamedPipes`, `CommunicationNamedPipesCommand`, and `TLV` retain the
reference helper APIs and wire format used by `commands_default`. Local defensive
changes bound IPC frame allocation, require complete frames, limit nested TLV
decoding, contain reader/callback exceptions, check command writes, and release
the pipe and reader even after failed startup or EOF. Optional callback readers
have pending Windows pipe I/O cancelled, are closed/unblocked, and are joined
before disposal returns.

Startup frame reads have a finite deadline: the positive connection timeout is
also the startup-read timeout, or 10 seconds when a nonpositive timeout was
requested. Timeout cancels/closes only the owned pipe and returns startup failure.
The one-shot timer is stopped and all queued/running callbacks are drained before
starting a reader or returning, including failed-read and validation paths.

Incoming updates must be leaf TLVs, and stop must be an empty leaf TLV. Malformed
command envelopes are rejected before invoking callbacks and are contained by
the reader failure boundary.

`CommandRuntime` is the local completion/cleanup owner for the benign echo
examples. It includes startup/configuration failures in the same boundary as
execution, attempts one checked terminal message on a usable connection, and
always disposes the client. More-data callbacks queue bounded FIFO input;
execution/output occur on the invocation thread, and queued updates preceding a
stop are processed before completion.

These source changes have not been compiled or run against the host. Full Docker
builds and managed DLL lifecycle verification remain required.
