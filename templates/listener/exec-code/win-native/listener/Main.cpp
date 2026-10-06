#include "../exec-unit-utils/CommunicationNamedPipes.h"

extern "C" __declspec(dllexport) void __cdecl start(const char* pipeName) {
    try {
        if (!pipeName || !*pipeName) return;
        CommunicationNamedPipes pipe(pipeName, {});
        const std::vector<byte> configuration = pipe.connect();
        if (!pipe.isConnected()) return;
        if (!configuration.empty()) return;
        // TODO: Add the data traffic channel using getMetadata(), getDataToSend()
        // and newDataFromC2(). The utility owns and joins the local pipe reader.
        while (pipe.isConnected()) Sleep(100);
    } catch (...) {
        // Scoped cleanup cancels I/O and joins the reader before DLL unload.
    }
}
