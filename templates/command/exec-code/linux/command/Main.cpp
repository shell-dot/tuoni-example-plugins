#include "../common/CommunicationNamedPipes.h"

#include <exception>
#include <stdexcept>
#include <string>
#include <vector>

namespace {
    void execute(CommunicationNamedPipes& client, const std::vector<uint8_t>& configuration) {
        // Add command behavior here. Send complete UTF-8 text payloads and
        // check delivery before run selects the terminal outcome.
        (void)configuration;
        const std::string result = "DONE";
        if (!client.sendResult(std::vector<uint8_t>(result.begin(), result.end())))
            throw std::runtime_error("Unable to send command result.");
    }
}

// The agent supplies FIFO paths. This library shares the agent's process.
extern "C" void run(char* pipeNameRead, char* pipeNameWrite) {
    if (!pipeNameRead || !pipeNameWrite)
        return; // No reporting channel can be established without the paths.

    try {
        // The destructor closes even after failed startup or reporting. No callbacks
        // are installed, so this no-op invocation owns no background workers.
        CommunicationNamedPipes client(pipeNameRead, pipeNameWrite);
        bool succeeded = false;
        try {
            const std::vector<uint8_t> configuration = client.connect();
            if (!configuration.empty())
                throw std::invalid_argument("The template command expects an empty configuration payload.");
            execute(client, configuration);
            succeeded = true;
        } catch (const std::exception& error) {
            // Failure to allocate/format/send a diagnostic must not skip completion.
            try {
                const std::string message(error.what());
                client.sendError(std::vector<uint8_t>(message.begin(), message.end()));
            } catch (...) { }
        } catch (...) {
            // Unknown operation failures still reach the same completion owner.
        }

        // Exactly one checked terminal attempt, including success with no output.
        // A broken channel cannot report; do not append/replay another terminal frame.
        const bool reported = succeeded ? client.sendReturnSuccess() : client.sendReturnFailed();
        if (!reported)
            return;
    } catch (...) {
        // Contain startup/reporting exceptions across the host entrypoint. Scoped
        // cleanup runs first; never terminate the host or let work survive return.
    }
}
