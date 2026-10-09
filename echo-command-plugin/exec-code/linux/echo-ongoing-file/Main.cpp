#include "../common/CommunicationNamedPipes.h"

#include <atomic>
#include <chrono>
#include <cstddef>
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

static bool sendText(CommunicationNamedPipes& pipe, const std::string& text) {
    return pipe.sendResult(Bytes(text.begin(), text.end()));
}

static bool executeCommand(CommunicationNamedPipes& pipe, const Bytes& configuration,
    const std::atomic<bool>& stopped) {
    if (configuration.size() < 4) {
        const std::string error = "File configuration is shorter than its line count";
        pipe.sendError(Bytes(error.begin(), error.end()));
        return false;
    }
    const uint32_t lines = uint32_t(configuration[0]) |
        (uint32_t(configuration[1]) << 8) |
        (uint32_t(configuration[2]) << 16) |
        (uint32_t(configuration[3]) << 24);
    if (lines == 0 || lines > 2147483647u) {
        const std::string error = "Lines per second must be positive";
        pipe.sendError(Bytes(error.begin(), error.end()));
        return false;
    }
    if (!pipe.sendConf_ongoingResult() || !pipe.sendConf_stoppable(10000)) return false;

    const std::string text(configuration.begin() + 4, configuration.end());
    std::size_t begin = 0;
    uint32_t count = 0;
    while (begin <= text.size()) {
        const std::size_t end = text.find('\n', begin);
        const std::size_t length = end == std::string::npos ? text.size() - begin : end - begin;
        if (!sendText(pipe, text.substr(begin, length) + "\n")) return false;
        ++count;
        if (count % lines == 0 && !pause(pipe, stopped)) return false;
        if (stopped.load()) {
            if (!sendText(pipe, "=== USER FORCED STOP ===\n")) return false;
            break;
        }
        if (end == std::string::npos) break;
        begin = end + 1;
    }
    return sendText(pipe, "Stopping now\n");
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
