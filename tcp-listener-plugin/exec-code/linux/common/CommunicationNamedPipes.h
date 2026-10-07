#include <atomic>
#include <cstddef>
#include <cstdint>
#include <thread>
#include <mutex>
#include <string>
#include <condition_variable>
#include <map>
#include <vector>
#include "TLV.h"

typedef void (CallbackFunc)(const std::vector<uint8_t>);

class CommunicationNamedPipes {
private:
    std::atomic<bool> active{false};
    int pipe_read = -1, pipe_write = -1;
    std::string pipeNameRead, pipeNameWrite;
    std::thread listen_thread;
    std::atomic<int> seqNr{1};
    std::map<int, std::shared_ptr<TLV>> responses;
    std::condition_variable responsesReady;
    std::mutex mtx;
    CallbackFunc* callback;
    bool readExact(void* buffer, size_t length);

public:
    CommunicationNamedPipes(const std::string &pipeNameReadIn, const std::string &pipeNameWriteIn, CallbackFunc* callbackIn)
        : pipeNameRead(pipeNameReadIn), pipeNameWrite(pipeNameWriteIn), callback(callbackIn) {}
    ~CommunicationNamedPipes() { close(); }

    void setCallback(CallbackFunc* callbackIn);
    std::vector<uint8_t> connect();
    void listenForMessages();
    std::vector<uint8_t> getData();
    bool putData(const std::vector<uint8_t> &data);
    void requestStop();
    void close();
    bool isConnected() const { return active.load(); }
    std::vector<uint8_t> getMetadata();
    std::vector<uint8_t> getDataToSend();
    std::vector<uint8_t> waitForResponseData(int id);
    void newDataFromC2(std::vector<uint8_t>);
};
