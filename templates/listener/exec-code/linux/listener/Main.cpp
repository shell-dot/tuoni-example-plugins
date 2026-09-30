#include "../common/CommunicationNamedPipes.h"

// The Linux agent supplies FIFO paths to this exported entry point.
extern "C" void run(char* pipeNameRead, char* pipeNameWrite) {
    if (!pipeNameRead || !pipeNameWrite)
        return;

    CommunicationNamedPipes pipe(pipeNameRead, pipeNameWrite, nullptr);
    // TODO: Connect to the agent with pipe.connect(), validate configuration,
    // register callbacks, and keep this function alive for the listener lifetime.
    // See tcp-listener-plugin/exec-code/linux/tcp-listener/Main.cpp for a
    // transport implementation.
}
