#include "../common/EchoRuntime.h"

#include <chrono>
#include <string>
#include <thread>

extern "C" void run(char* pipeNameRead, char* pipeNameWrite) {
    runEcho(pipeNameRead, pipeNameWrite,
            [](CommunicationNamedPipes& client, const std::vector<uint8_t>& data) {
                client.sendConf_ongoingResult();
                const std::string message(data.begin(), data.end());
                for (int counter = 0; counter < 4; ++counter) {
                    client.sendResult(echoBytes(std::to_string(counter) + ": " + message + "\n"));
                    std::this_thread::sleep_for(std::chrono::seconds(1));
                }
                client.sendResult(echoBytes("Stopping now\n"));
                return true;
            });
}
