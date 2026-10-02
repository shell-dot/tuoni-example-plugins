#include "../common/CommunicationNamedPipes.h"

#include <chrono>
#include <thread>
#include <vector>

// The Linux agent supplies FIFO paths to this exported entry point.
// This is a host-loaded library entrypoint, not a standalone process. Copy borrowed
// paths if owned workers need them, install RAII cleanup before constructing or
// connecting the runtime, and contain ordinary exceptions across the exported body
// and worker/callback boundaries. No exception or invocation-owned work may survive
// return, and operation/reporting failure must never terminate the host process.
extern "C" void run(char* pipeNameRead, char* pipeNameWrite) {
    if (!pipeNameRead || !pipeNameWrite)
        return;

    CommunicationNamedPipes client(pipeNameRead, pipeNameWrite);
    const std::vector<uint8_t> configuration = client.connect();
    (void)configuration;

    // TODO: Validate configuration and implement the command. Use sendResult()
    // for output, then sendReturnSuccess() when the command completes.
    // configuration is the inner payload emitted by both Java generation methods;
    // connect already removes the host frame/envelope. Decode the agreed format with
    // bounds and encoding checks before executing; distinguish valid empty input from
    // failed connection (the current helper returns an empty vector for both).
    // Encode results for TemplateCommand.parseResult and preserve earlier output when
    // streaming. Register any update/stop callbacks before connect and advertise their
    // handling options before output. Use one completion owner for success, failure,
    // cancellation and early returns: drain operation work/results, send exactly one
    // checked terminal outcome on a usable channel, then stop/unblock/drain and join
    // all remaining transport work before closing resources. Diagnostic text alone
    // does not complete a failure, and zero output still requires success completion.
    // Review the shared helpers before relying on them: their sends discard write
    // status, writes may be partial, and their optional reader is detached. Propagate
    // complete-frame outcomes, bound I/O and protect FIFO writes against host-fatal
    // SIGPIPE without changing process-wide signal handling. See docs/native-runtime.md.
    const char error[] = "Command execution is not implemented.";
    client.sendError(std::vector<uint8_t>(error, error + sizeof(error) - 1));
    client.sendReturnFailed();

    // Allow the agent to drain the final IPC messages, as in the echo example.
    // This scaffold delay does not prove delivery or asynchronous-worker shutdown.
    // Replace it with the actual transport's checked write/drain and cleanup contract
    // when implementing the command; do not invent a new acknowledgment message.
    std::this_thread::sleep_for(std::chrono::seconds(4));
    client.close();
}
