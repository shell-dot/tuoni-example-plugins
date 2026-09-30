#include "../common/CommunicationNamedPipes.h"

#include <chrono>
#include <thread>
#include <vector>

// The Linux agent supplies FIFO paths to this exported entry point.
extern "C" void run(char* pipeNameRead, char* pipeNameWrite) {
    if (!pipeNameRead || !pipeNameWrite)
        return;

    CommunicationNamedPipes client(pipeNameRead, pipeNameWrite);
    const std::vector<uint8_t> configuration = client.connect();
    (void)configuration;

    // TODO: Validate configuration and implement the command. Use sendResult()
    // for output, then sendReturnSuccess() when the command completes.
    const char error[] = "Command execution is not implemented.";
    client.sendError(std::vector<uint8_t>(error, error + sizeof(error) - 1));
    client.sendReturnFailed();

    // Allow the agent to drain the final IPC messages, as in the echo example.
    std::this_thread::sleep_for(std::chrono::seconds(4));
    client.close();
}
