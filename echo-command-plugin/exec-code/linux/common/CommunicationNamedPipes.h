#pragma once

#include <cstdint>
#include <atomic>
#include <cstddef>
#include <functional>
#include <mutex>
#include <string>
#include <thread>
#include <vector>

#include "TLV.h"

class CommunicationNamedPipes {
private:
    std::atomic<bool> active{false};
    bool listenerStarted = false;
    int pipe_read = -1;
    int pipe_write = -1;
    std::string pipeNameRead;
    std::string pipeNameWrite;
    std::mutex mtx;
    std::thread listen_thread;
    std::function<void(const std::vector<uint8_t>&)> callbackNewData;
    std::function<void()> callbackStop;

    void startListenerIfNeeded();
    bool readExact(void* buffer, std::size_t size);

public:
    CommunicationNamedPipes(const std::string &pipeNameReadIn, const std::string &pipeNameWriteIn)
        : pipeNameRead(pipeNameReadIn), pipeNameWrite(pipeNameWriteIn) {}

    ~CommunicationNamedPipes() { close(); }
    void setCallbackNewData(std::function<void(const std::vector<uint8_t>&)> callbackIn);
    void setCallbackStop(std::function<void()> callbackIn);
    bool isConnected() const { return active.load(); }
    std::vector<uint8_t> connect();
    std::vector<uint8_t> getData();
    bool putData(const std::vector<uint8_t> &data);
    void close();
    bool sendResult(const std::vector<uint8_t> &data);
    bool sendError(const std::vector<uint8_t> &data);
    bool sendReturnSuccess();
    bool sendReturnFailed();
    bool sendConf_ongoingResult();
    bool sendConf_relayInBlocks();
    bool sendConf_stoppable(uint32_t waitTime);
    void listenForMessages();
};
