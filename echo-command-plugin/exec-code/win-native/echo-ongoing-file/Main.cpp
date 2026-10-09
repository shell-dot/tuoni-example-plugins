#include "../exec-unit-utils/CommunicationNamedPipesCommand.h"

#include <atomic>
#include <cstdint>
#include <string>
#include <vector>

using Bytes = std::vector<std::uint8_t>;

static bool pause(ExecUnitUtils::CommunicationNamedPipesCommand& pipe,
    const std::atomic<bool>& stopped) {
    const ULONGLONG deadline = GetTickCount64() + 1000;
    while (!stopped.load() && GetTickCount64() < deadline) {
        if (!pipe.isConnected()) return false;
        Sleep(25);
    }
    return true;
}

static bool sendText(ExecUnitUtils::CommunicationNamedPipesCommand& pipe,
    const std::string& text) {
    return pipe.sendResult(Bytes(text.begin(), text.end()));
}

static bool executeCommand(ExecUnitUtils::CommunicationNamedPipesCommand& pipe,
    const Bytes& configuration, const std::atomic<bool>& stopped) {
    if (configuration.size() < 4) {
        const std::string error = "File configuration is shorter than its line count";
        pipe.sendError(Bytes(error.begin(), error.end()));
        return false;
    }
    const std::uint32_t lines = std::uint32_t(configuration[0]) |
        (std::uint32_t(configuration[1]) << 8) |
        (std::uint32_t(configuration[2]) << 16) |
        (std::uint32_t(configuration[3]) << 24);
    if (lines == 0 || lines > 2147483647u) {
        const std::string error = "Lines per second must be positive";
        pipe.sendError(Bytes(error.begin(), error.end()));
        return false;
    }
    if (!pipe.sendConf_ongoingResult() || !pipe.sendConf_stoppable(10000)) return false;

    const std::string text(configuration.begin() + 4, configuration.end());
    std::size_t begin = 0;
    std::uint32_t count = 0;
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

extern "C" __declspec(dllexport) void __cdecl start(const char* pipeName) {
    if (!pipeName || !*pipeName) return;
    std::atomic<bool> stopped{false};
    auto options = ExecUnitUtils::CommunicationNamedPipesOptions::structuredCommand();
    options.maxInboundFrameBytes = 64u * 1024u * 1024u;
    ExecUnitUtils::CommunicationNamedPipesCommand pipe(pipeName, {},
        [&stopped]() { stopped.store(true); }, options);
    Bytes configuration;
    if (!pipe.TryConnect(configuration)) return;

    bool success = false;
    success = executeCommand(pipe, configuration, stopped);
    if (!pipe.isConnected()) return;
    const bool completed = success ? pipe.sendReturnSuccess() : pipe.sendReturnFailed();
    if (!completed) return;
}
