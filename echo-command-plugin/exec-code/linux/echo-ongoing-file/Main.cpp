#include "../common/EchoRuntime.h"

#include <atomic>
#include <chrono>
#include <cstddef>
#include <cstdint>
#include <stdexcept>
#include <string>
#include <thread>

namespace {
std::atomic<bool> stopped(false);

void stop() {
    stopped.store(true);
}
}

extern "C" void run(char* pipeNameRead, char* pipeNameWrite) {
    stopped.store(false);
    runEcho(pipeNameRead, pipeNameWrite,
            [](CommunicationNamedPipes& client, const std::vector<uint8_t>& data) {
                if (data.size() < 4)
                    throw std::runtime_error("File configuration is shorter than its line count");
                const uint32_t lines = static_cast<uint32_t>(data[0]) |
                                       (static_cast<uint32_t>(data[1]) << 8) |
                                       (static_cast<uint32_t>(data[2]) << 16) |
                                       (static_cast<uint32_t>(data[3]) << 24);
                if (lines == 0)
                    throw std::runtime_error("Lines per second must be positive");

                client.setCallbackStop(stop);
                client.sendConf_ongoingResult();
                client.sendConf_stoppable(10000);

                const std::string content(data.begin() + 4, data.end());
                std::size_t begin = 0;
                uint32_t count = 0;
                while (begin <= content.size()) {
                    const std::size_t end = content.find('\n', begin);
                    const std::size_t length = end == std::string::npos ? content.size() - begin : end - begin;
                    client.sendResult(echoBytes(content.substr(begin, length) + "\n"));
                    ++count;
                    if (count % lines == 0)
                        std::this_thread::sleep_for(std::chrono::seconds(1));
                    if (stopped.load()) {
                        client.sendResult(echoBytes("=== USER FORCED STOP ===\n"));
                        break;
                    }
                    if (end == std::string::npos)
                        break;
                    begin = end + 1;
                }
                client.sendResult(echoBytes("Stopping now\n"));
                return true;
            });
}
