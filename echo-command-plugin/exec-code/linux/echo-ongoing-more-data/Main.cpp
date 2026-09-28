#include "../common/EchoRuntime.h"

#include <atomic>
#include <condition_variable>
#include <mutex>
#include <string>

namespace {
std::atomic<bool> stopped(false);
std::atomic<bool> failed(false);
std::mutex stopMutex;
std::condition_variable stopCondition;
CommunicationNamedPipes* activeClient = nullptr;

void stop() {
    stopped.store(true);
    stopCondition.notify_all();
}

void newData(const std::vector<uint8_t> data) {
    if (data.empty() || (data.size() == 1 && data[0] == 0)) {
        stop();
        return;
    }
    try {
        activeClient->sendResult(echoBytes("New data: " + std::string(data.begin(), data.end()) + "\n"));
    } catch (const std::exception& error) {
        activeClient->sendError(echoBytes(error.what()));
        failed.store(true);
        stop();
    }
}
}

extern "C" void run(char* pipeNameRead, char* pipeNameWrite) {
    stopped.store(false);
    failed.store(false);
    runEcho(pipeNameRead, pipeNameWrite,
            [](CommunicationNamedPipes& client, const std::vector<uint8_t>& data) {
                activeClient = &client;
                client.setCallbackNewData(newData);
                client.setCallbackStop(stop);
                client.sendConf_ongoingResult();
                client.sendConf_stoppable(10000);
                client.sendResult(echoBytes("Initial data: " + std::string(data.begin(), data.end()) + "\n"));
                std::unique_lock<std::mutex> lock(stopMutex);
                stopCondition.wait(lock, [] { return stopped.load(); });
                return !failed.load();
            });
    activeClient = nullptr;
}
