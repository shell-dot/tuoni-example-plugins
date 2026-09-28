#include "../common/EchoRuntime.h"

#include <stdexcept>
#include <string>

extern "C" void run(char* pipeNameRead, char* pipeNameWrite) {
    runEcho(pipeNameRead, pipeNameWrite,
            [](CommunicationNamedPipes& client, const std::vector<uint8_t>& data) {
                const std::string message(data.begin(), data.end());
                if (message.compare(0, 4, "ERR:") == 0)
                    throw std::runtime_error("Simulated exception: " + message.substr(4));
                client.sendResult(data);
                return true;
            });
}
