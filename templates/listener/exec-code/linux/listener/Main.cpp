#include "../common/CommunicationNamedPipes.h"

// The Linux agent supplies FIFO paths to this exported entry point.
extern "C" void run(char* pipeNameRead, char* pipeNameWrite) {
    if (!pipeNameRead || !pipeNameWrite)
        return;

    CommunicationNamedPipes pipe(pipeNameRead, pipeNameWrite, nullptr);
    // TODO: Connect to the agent with pipe.connect(), validate configuration,
    // register callbacks, and keep this function alive for the listener lifetime.
    // See tcp-listener-plugin/exec-code/linux/tcp-listener/Main.cpp for a
    // transport implementation.
    // Register the host callback before connect() starts its reader. The supplied
    // FIFO paths belong to the local agent; connect() performs its readiness/frame
    // exchange and returns inner configuration bytes from Java. Decode those bytes
    // separately from host TLV framing, then open the chosen application transport
    // to Java. Forward agent metadata/requests to that transport and return opaque
    // Java command bytes through newDataFromC2(); do not mix custom telemetry into
    // SDK-owned data. Verify host 0x20 semantics before treating it as an update.
    // Install invocation ownership/rollback before acquisition and contain all C++
    // exceptions across the entire export, including setup and reporting. On every
    // failure, cancellation, or disconnect, unblock I/O/response waits, unregister
    // and drain callbacks, join all workers, and close/reset resources before return.
    // Audit/repair the included helper for partial I/O, bounded frames, waiter
    // cancellation, repeated close, and per-thread FIFO SIGPIPE handling before use;
    // its current close() alone does not establish safe immediate unload.
}
