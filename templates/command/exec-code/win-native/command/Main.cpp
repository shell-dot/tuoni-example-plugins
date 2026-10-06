#include "../common/CommandRuntime.h"

extern "C" __declspec(dllexport) void __cdecl start(const char* pipeName) {
    commandexample::runCommand(pipeName, [](commandexample::CommandChannel& pipe,
        const commandexample::Bytes& configuration, commandexample::CommandInput&,
        std::string& error) {
        if (!configuration.empty()) {
            error = "The template command expects an empty configuration payload.";
            return false;
        }
        if (!pipe.sendResult(commandexample::textBytes("DONE"))) {
            error = "Agent pipe write failed";
            return false;
        }
        return true;
    });
}
