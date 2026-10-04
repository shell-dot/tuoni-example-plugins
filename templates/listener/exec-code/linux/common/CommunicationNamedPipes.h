#include <iostream>
#include <atomic>
#include <fcntl.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <unistd.h>
#include <thread>
#include <mutex>
#include <condition_variable>
#include <map>
#include <cstring>
#include <vector>
#include <semaphore.h>
#include "TLV.h" // Assuming you have a similar TLV class implemented in C++

typedef void (CallbackFunc)(const std::vector<uint8_t>);

class CommunicationNamedPipes {
private:
    std::atomic<bool> active{false};
    int pipe_read = -1, pipe_write = -1;
    std::string pipeNameRead, pipeNameWrite;
    std::thread listen_thread;
    std::atomic<int> seqNr{1};
    std::map<int, std::shared_ptr<TLV>> responses;
    std::map<int, sem_t> signal;
    std::mutex mtx;
    CallbackFunc* callback;

public:
    // Retain the two local-agent FIFO paths and optional host-message callback;
    // this constructor does not open descriptors or start a reader. The invocation
    // owner connects later and keeps the helper alive until its reader finishes.
    CommunicationNamedPipes(const std::string &pipeNameReadIn, const std::string &pipeNameWriteIn, CallbackFunc* callbackIn)
        : pipeNameRead(pipeNameReadIn), pipeNameWrite(pipeNameWriteIn), callback(callbackIn) {}
    ~CommunicationNamedPipes() { close(); }

    void setCallback(CallbackFunc* callbackIn);
    std::vector<uint8_t> connect();
    void listenForMessages();
    std::vector<uint8_t> getData();
    bool putData(const std::vector<uint8_t> &data);
    void close();
    void waitForDisconnect();
    std::vector<uint8_t> getMetadata();
    std::vector<uint8_t> getDataToSend();
    std::vector<uint8_t> waitForResponseData(int id);
    void newDataFromC2(std::vector<uint8_t>);
};
