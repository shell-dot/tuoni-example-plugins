#include "../exec-unit-utils/CommunicationNamedPipesCommand.h"

#include <cstdint>
#include <string>
#include <vector>

using Bytes = std::vector<std::uint8_t>;

static bool executeCommand(ExecUnitUtils::CommunicationNamedPipesCommand& pipe,
    const Bytes& configuration) {
    const std::string text(configuration.begin(), configuration.end());
    return pipe.sendResult(configuration);
}

extern "C" __declspec(dllexport) void __cdecl start(const char* pipeName) {
    if (!pipeName || !*pipeName) return;
    auto options = ExecUnitUtils::CommunicationNamedPipesOptions::structuredCommand();
    options.maxInboundFrameBytes = 64u * 1024u * 1024u;
    ExecUnitUtils::CommunicationNamedPipesCommand pipe(pipeName, {}, {}, options);
    Bytes configuration;
    if (!pipe.TryConnect(configuration)) return;

    bool success = false;
    success = executeCommand(pipe, configuration);
    if (!pipe.isConnected()) return;
    const bool completed = success ? pipe.sendReturnSuccess() : pipe.sendReturnFailed();
    if (!completed) return;
}
