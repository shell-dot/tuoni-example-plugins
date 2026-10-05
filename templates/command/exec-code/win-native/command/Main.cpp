#include "../common/CommandRuntime.h"

extern "C" __declspec(dllexport) void __cdecl start(const char* pipeName) {
    commandexample::runCommand(pipeName, [](commandexample::CommandChannel& pipe,
        const commandexample::Bytes& configuration, commandexample::CommandInput&) {
        if (!configuration.empty())
            throw std::invalid_argument("The template command expects an empty configuration payload.");
        commandexample::requireSend(pipe.sendResult(commandexample::textBytes("DONE")));
    });
}
