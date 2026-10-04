#pragma once

#include <cstdint>
#include <mutex>
#include <string>
#include <thread>
#include <vector>

#include "TLV.h"

typedef void (CallbackFunc)(const std::vector<uint8_t>);
typedef void (CallbackFuncStop)();

class CommunicationNamedPipes {
private:
    bool active = false;
    bool listenerStarted = false;
    int pipe_read = -1;
    int pipe_write = -1;
    std::string pipeNameRead;
    std::string pipeNameWrite;
    std::mutex mtx;
    std::thread listen_thread;
    CallbackFunc* callbackNewData = nullptr;
    CallbackFuncStop* callbackStop = nullptr;

    void startListenerIfNeeded();

public:
    CommunicationNamedPipes(const std::string &pipeNameReadIn, const std::string &pipeNameWriteIn)
        : pipeNameRead(pipeNameReadIn), pipeNameWrite(pipeNameWriteIn) {}
    ~CommunicationNamedPipes() { close(); }

    void setCallback(CallbackFunc* callbackIn);
    void setCallbackNewData(CallbackFunc* callbackIn);
    void setCallbackStop(CallbackFuncStop* callbackIn);
    std::vector<uint8_t> connect();
    std::vector<uint8_t> getData();
    bool putData(const std::vector<uint8_t> &data);
    void close();
    bool sendResult(const std::vector<uint8_t> &data);
    bool sendError(const std::vector<uint8_t> &data);
    bool sendReturnSuccess();
    bool sendReturnFailed();
    void sendConf_ongoingResult();
    void sendConf_relayInBlocks();
    void sendConf_stoppable(uint32_t waitTime);
    void listenForMessages();
};
