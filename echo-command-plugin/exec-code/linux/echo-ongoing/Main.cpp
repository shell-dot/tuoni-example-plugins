#include "../common/CommunicationNamedPipes.h"

#include <atomic>
#include <chrono>
#include <cstdint>
#include <string>
#include <thread>
#include <vector>

using Bytes = std::vector<uint8_t>;

static bool pause(CommunicationNamedPipes& pipe, const std::atomic<bool>& stopped) {
    const auto deadline = std::chrono::steady_clock::now() + std::chrono::seconds(1);
    while (!stopped.load() && std::chrono::steady_clock::now() < deadline) {
        if (!pipe.isConnected()) return false;
        std::this_thread::sleep_for(std::chrono::milliseconds(25));
    }
    return true;
}

static bool executeCommand(CommunicationNamedPipes& pipe, const Bytes& configuration,
    const std::atomic<bool>& stopped) {
    if (!pipe.sendConf_ongoingResult()) return false;
    const std::string text(configuration.begin(), configuration.end());
    for (int counter = 0; counter < 4 && !stopped.load(); ++counter) {
        const std::string line = std::to_string(counter) + ": " + text + "\n";
        if (!pipe.sendResult(Bytes(line.begin(), line.end()))) return false;
        if (!pause(pipe, stopped)) return false;
    }
    const std::string ending = "Stopping now\n";
    return pipe.sendResult(Bytes(ending.begin(), ending.end()));
}

extern "C" void run(char* pipeNameRead, char* pipeNameWrite) {
    if (!pipeNameRead || !pipeNameWrite) return;
    std::atomic<bool> stopped{false};
    CommunicationNamedPipes pipe(pipeNameRead, pipeNameWrite);
    pipe.setCallbackStop([&stopped]() { stopped.store(true); });
    const Bytes configuration = pipe.connect();
    if (!pipe.isConnected()) return;

    bool success = false;
    success = executeCommand(pipe, configuration, stopped);
    if (!pipe.isConnected()) return;
    const bool completed = success ? pipe.sendReturnSuccess() : pipe.sendReturnFailed();
    if (!completed) return;
    std::this_thread::sleep_for(std::chrono::seconds(4));
    pipe.close();
}
