#include "../common/EchoRuntime.h"

extern "C" __declspec(dllexport) void __cdecl start(const char* pipeName) {
    commandexample::runCommand(pipeName, echoexample::echo);
}
