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

static bool executeCommand(ExecUnitUtils::CommunicationNamedPipesCommand& pipe,
    const Bytes& configuration, const std::atomic<bool>& stopped) {
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
