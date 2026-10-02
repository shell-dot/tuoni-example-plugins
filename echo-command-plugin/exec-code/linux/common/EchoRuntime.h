#pragma once

#include "CommunicationNamedPipes.h"

#include <chrono>
#include <cstdint>
#include <exception>
#include <string>
#include <thread>
#include <vector>

inline std::vector<uint8_t> echoBytes(const std::string& value) {
    return std::vector<uint8_t>(value.begin(), value.end());
}

template <typename Execute>
void runEcho(char* pipeNameRead, char* pipeNameWrite, Execute execute) {
    if (!pipeNameRead || !pipeNameWrite)
        return;

    CommunicationNamedPipes client(pipeNameRead, pipeNameWrite);
    const std::vector<uint8_t> configuration = client.connect();
    try {
        if (execute(client, configuration))
            client.sendReturnSuccess();
        else
            client.sendReturnFailed();
    } catch (const std::exception& error) {
        client.sendError(echoBytes(error.what()));
        client.sendReturnFailed();
    }

    // Match the Windows example's drain interval before closing the command pipe.
    std::this_thread::sleep_for(std::chrono::seconds(4));
    client.close();
}
