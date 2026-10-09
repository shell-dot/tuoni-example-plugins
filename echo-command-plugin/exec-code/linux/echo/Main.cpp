#include "../common/CommunicationNamedPipes.h"

#include <cstdint>
#include <string>
#include <thread>
#include <chrono>
#include <vector>

using Bytes = std::vector<uint8_t>;

static bool executeCommand(CommunicationNamedPipes& pipe, const Bytes& configuration) {
    const std::string text(configuration.begin(), configuration.end());
    return pipe.sendResult(configuration);
}

extern "C" void run(char* pipeNameRead, char* pipeNameWrite) {
    if (!pipeNameRead || !pipeNameWrite) return;
    CommunicationNamedPipes pipe(pipeNameRead, pipeNameWrite);
    const Bytes configuration = pipe.connect();
    if (!pipe.isConnected()) return;

    bool success = false;
    success = executeCommand(pipe, configuration);
    if (!pipe.isConnected()) return;
    const bool completed = success ? pipe.sendReturnSuccess() : pipe.sendReturnFailed();
    if (!completed) return;
    std::this_thread::sleep_for(std::chrono::seconds(4));
    pipe.close();
}
