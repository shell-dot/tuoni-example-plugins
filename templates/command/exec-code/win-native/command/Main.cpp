#include "../exec-unit-utils/CommunicationNamedPipesCommand.h"

#include <cstdint>
#include <string>
#include <vector>

extern "C" __declspec(dllexport) void __cdecl start(const char* pipeName) {
    try {
        if (!pipeName || !*pipeName) return;

        auto options = ExecUnitUtils::CommunicationNamedPipesOptions::structuredCommand();
        options.maxInboundFrameBytes = 64u * 1024u * 1024u;
        ExecUnitUtils::CommunicationNamedPipesCommand pipe(pipeName, {}, {}, options);

        bool success = false;
        try {
            std::vector<std::uint8_t> configuration;
            if (!pipe.TryConnect(configuration)) return;

            if (!configuration.empty()) {
                const std::string message = "The template command expects an empty configuration payload.";
                const std::vector<std::uint8_t> error(message.begin(), message.end());
                if (!pipe.sendError(error)) return;
            } else {
                const std::vector<std::uint8_t> result = {'D', 'O', 'N', 'E'};
                if (!pipe.sendResult(result)) return;
                success = true;
            }
        } catch (...) {
            // A library failure can still leave the pipe usable for failure completion.
        }

        // The utility closes the pipe and joins its reader when it leaves scope.
        const bool completed = success ? pipe.sendReturnSuccess() : pipe.sendReturnFailed();
        if (!completed) return;
    } catch (...) {
        // No C++ exception may escape the DLL entry point.
    }
}
