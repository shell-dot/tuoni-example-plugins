#include "../common/CommunicationNamedPipes.h"

#include <stdexcept>
#include <vector>

namespace {
    void serve(CommunicationNamedPipes& pipe, const std::vector<uint8_t>& configuration) {
        (void)configuration;
        // TODO: Open the data traffic channel, forward agent metadata/requests to
        // Java, and return queued commands through newDataFromC2.
        // For a traffic-channel example, see
        // tcp-listener-plugin/exec-code/linux/tcp-listener/Main.cpp.
        // The idle default makes no traffic requests and remains alive until the
        // local agent closes its FIFO. Wait for the owned reader to finish.
        pipe.waitForDisconnect();
    }
}

// The Linux agent supplies FIFO paths to this host-loaded entrypoint.
extern "C" void run(char* pipeNameRead, char* pipeNameWrite) {
    if (!pipeNameRead || !pipeNameWrite)
        return;

    try {
        // Scoped ownership closes and joins the reader after startup failure,
        // validation failure, or normal disconnect before code can be unloaded.
        CommunicationNamedPipes pipe(pipeNameRead, pipeNameWrite, nullptr);
        const std::vector<uint8_t> configuration = pipe.connect();
        if (!configuration.empty())
            throw std::invalid_argument("The template listener expects an empty configuration payload.");
        serve(pipe, configuration);
    } catch (...) {
        // Never let a listener failure escape into or terminate the agent host.
    }
}
