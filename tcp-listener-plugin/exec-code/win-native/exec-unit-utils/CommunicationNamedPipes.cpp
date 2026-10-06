#include "CommunicationNamedPipes.h"

#include <algorithm>
#include <cstdint>
#include <utility>
#include <limits>

// Imported from listeners_default; local changes enforce the template's bounded
// I/O and joined-reader requirements. See README.md beside this source.
namespace {
const std::size_t maxFrameBytes = 64u * 1024u * 1024u;

// Validate the complete envelope before the reference TLV parser allocates nodes.
bool validEnvelope(const byte* bytes, std::size_t size, unsigned depth, unsigned& nodes) {
    if (size < 5 || depth > 64 || ++nodes > 4096) return false;
    std::uint32_t length = 0;
    std::memcpy(&length, bytes + 1, sizeof(length));
    if (length != size - 5) return false;
    if (!(bytes[0] & TLV_PARENT_TYPE_FLAG)) return true;
    std::size_t offset = 5;
    while (offset < size) {
        if (size - offset < 5) return false;
        std::uint32_t childLength = 0;
        std::memcpy(&childLength, bytes + offset + 1, sizeof(childLength));
        if (childLength > size - offset - 5 ||
            !validEnvelope(bytes + offset, std::size_t(childLength) + 5, depth + 1, nodes))
            return false;
        offset += std::size_t(childLength) + 5;
    }
    return true;
}

bool validEnvelope(const std::vector<byte>& bytes) {
    unsigned nodes = 0;
    return validEnvelope(bytes.data(), bytes.size(), 0, nodes);
}

// The event, OVERLAPPED and caller buffer stay alive until completion, including
// cancellation. The owner keeps hPipe open until the reader and writer finish.
bool transfer(HANDLE pipe, HANDLE shutdown, void* buffer, DWORD size,
    bool writing, DWORD timeout, DWORD& transferred) {
    OVERLAPPED operation = {};
    operation.hEvent = CreateEventW(nullptr, TRUE, FALSE, nullptr);
    if (!operation.hEvent) return false;
    transferred = 0;
    BOOL success = writing
        ? WriteFile(pipe, buffer, size, &transferred, &operation)
        : ReadFile(pipe, buffer, size, &transferred, &operation);
    if (!success && GetLastError() == ERROR_IO_PENDING) {
        HANDLE events[] = {operation.hEvent, shutdown};
        if (WaitForMultipleObjects(2, events, FALSE, timeout) == WAIT_OBJECT_0) {
            success = GetOverlappedResult(pipe, &operation, &transferred, FALSE);
        } else {
            CancelIoEx(pipe, &operation);
            GetOverlappedResult(pipe, &operation, &transferred, TRUE);
            success = FALSE;
        }
    }
    CloseHandle(operation.hEvent);
    return success && transferred != 0;
}

bool writeOverlapped(HANDLE pipe, HANDLE shutdown, const void* buffer, DWORD length) {
    const ULONGLONG deadline = GetTickCount64() + 10000;
    DWORD total = 0;
    while (total < length) {
        const ULONGLONG now = GetTickCount64();
        if (now >= deadline || WaitForSingleObject(shutdown, 0) != WAIT_TIMEOUT) return false;
        DWORD written = 0;
        if (!transfer(pipe, shutdown,
            const_cast<byte*>(static_cast<const byte*>(buffer)) + total,
            (std::min)(length - total, DWORD(65536)), true,
            static_cast<DWORD>(deadline - now), written)) return false;
        total += written;
    }
    return true;
}
}

CommunicationNamedPipes::CommunicationNamedPipes(const std::string& name,
    std::function<void(const std::vector<byte>&)> callbackIn)
{
    pipePath = "\\\\.\\pipe\\" + name;
    callback = std::move(callbackIn);
    InitializeCriticalSection(&csResponses);
    InitializeCriticalSection(&csWrite);
    shutdownEvent = CreateEventW(nullptr, TRUE, FALSE, nullptr);
    // connect() checks this handle and reports startup failure to the caller.
}

CommunicationNamedPipes::~CommunicationNamedPipes()
{
    close();
    for (auto& pair : signals) CloseHandle(pair.second);
    if (shutdownEvent) CloseHandle(shutdownEvent);
    DeleteCriticalSection(&csResponses);
    DeleteCriticalSection(&csWrite);
}

void CommunicationNamedPipes::setCallback(std::function<void(const std::vector<byte>&)> callbackIn)
{
    CriticalSectionGuard lock(csResponses);
    callback = std::move(callbackIn);
}

void CommunicationNamedPipes::requestStop() noexcept
{
    active.store(false);
    if (shutdownEvent) SetEvent(shutdownEvent);
}

bool CommunicationNamedPipes::readExact(BYTE* buf, DWORD len, int timeoutMs)
{
    const ULONGLONG deadline = GetTickCount64() + (timeoutMs < 0 ? 0 : timeoutMs);
    DWORD totalRead = 0;
    while (totalRead < len && active.load()) {
        const ULONGLONG now = GetTickCount64();
        if (timeoutMs >= 0 && now >= deadline) return false;
        DWORD bytesRead = 0;
        if (!transfer(hPipe, shutdownEvent, buf + totalRead,
            (std::min)(len - totalRead, DWORD(65536)), false,
            timeoutMs < 0 ? INFINITE : static_cast<DWORD>(deadline - now), bytesRead))
            return false;
        totalRead += bytesRead;
    }
    return totalRead == len;
}

std::vector<byte> CommunicationNamedPipes::getData(bool initialFrame)
{
    if (!active.load()) return {};
    INT32 len = 0;
    auto* prefix = reinterpret_cast<BYTE*>(&len);
    // Idle readers wait for the first byte; partial frames have a finite deadline.
    if (!readExact(prefix, 1, initialFrame ? 10000 : -1) ||
        !readExact(prefix + 1, sizeof(len) - 1) ||
        len < 5 || static_cast<std::size_t>(len) > maxFrameBytes) {
        requestStop();
        return {};
    }
    std::vector<byte> data(static_cast<std::size_t>(len));
    if (!readExact(data.data(), static_cast<DWORD>(data.size())) || !validEnvelope(data)) {
        requestStop();
        return {};
    }
    return data;
}

bool CommunicationNamedPipes::putData(const std::vector<byte>& data)
{
    CriticalSectionGuard lock(csWrite);
    if (!active.load() || data.empty() || data.size() > maxFrameBytes) return false;
    INT32 len = static_cast<INT32>(data.size());
    if (!writeOverlapped(hPipe, shutdownEvent, &len, sizeof(len)) ||
        !writeOverlapped(hPipe, shutdownEvent, data.data(), static_cast<DWORD>(data.size()))) {
        requestStop();
        return false;
    }
    return true;
}

std::vector<byte> CommunicationNamedPipes::connect()
{
    if (!shutdownEvent || hPipe != INVALID_HANDLE_VALUE) return {};
    hPipe = CreateFileA(pipePath.c_str(), GENERIC_READ | GENERIC_WRITE,
        0, nullptr, OPEN_EXISTING, FILE_FLAG_OVERLAPPED, nullptr);
    if (hPipe == INVALID_HANDLE_VALUE) return {};
    DWORD mode = PIPE_READMODE_BYTE;
    if (!SetNamedPipeHandleState(hPipe, &mode, nullptr, nullptr)) {
        close();
        return {};
    }
    active.store(true);
    std::vector<byte> data = getData(true);
    TLVPtr tlv = std::make_shared<TLV>();
    if (data.empty() || !tlv->load(data) || tlv->isParent()) {
        close();
        return {};
    }
    std::vector<byte> configuration = tlv->getBytes();
    listenThread = CreateThread(nullptr, 0, listenThreadProc, this, 0, &listenThreadId);
    if (!listenThread) {
        close();
        return {};
    }
    return configuration;
}

DWORD WINAPI CommunicationNamedPipes::listenThreadProc(LPVOID param)
{
    auto* self = static_cast<CommunicationNamedPipes*>(param);
    try { self->listenForMessages(); } catch (...) { }
    self->requestStop();
    return 0;
}

void CommunicationNamedPipes::listenForMessages()
{
    while (active.load()) {
        std::vector<byte> data = getData();
        if (data.empty()) return;
        TLVPtr tlv = std::make_shared<TLV>();
        if (!tlv->load(data)) return;
        if (tlv->getType() == 0x20) {
            std::function<void(const std::vector<byte>&)> action;
            {
                CriticalSectionGuard lock(csResponses);
                action = callback;
            }
            TLVPtr child = tlv->getChild(0x4);
            if (action && child && !child->isParent()) action(child->getBytes());
            continue;
        }
        if ((tlv->getType() == 0x21 || tlv->getType() == 0x22) &&
            tlv->count(0x2) == 1 && tlv->count(0x4) <= 1) {
            INT32 id = 0;
            if (!tlv->getChild(0x2)->getValue<INT32>(id)) continue;
            CriticalSectionGuard lock(csResponses);
            // Only retain a response for a request reserved by the caller.
            if (signals.count(id) && !responses.count(id)) {
                responses[id] = tlv;
                SetEvent(signals[id]);
            }
        }
    }
}

void CommunicationNamedPipes::close() noexcept
{
    requestStop();
    if (hPipe != INVALID_HANDLE_VALUE) CancelIoEx(hPipe, nullptr);
    // Callbacks may request shutdown, but only the external owner destroys this object.
    if (listenThread && GetCurrentThreadId() == listenThreadId) return;
    if (listenThread) {
        WaitForSingleObject(listenThread, INFINITE);
        CloseHandle(listenThread);
        listenThread = nullptr;
    }
    CriticalSectionGuard lock(csWrite);
    if (hPipe != INVALID_HANDLE_VALUE) {
        CloseHandle(hPipe);
        hPipe = INVALID_HANDLE_VALUE;
    }
}

std::vector<byte> CommunicationNamedPipes::sendRequestAndWait(UINT8 messageType)
{
    if (!active.load()) return {};
    TLVPtr tlv = std::make_shared<TLV>(messageType);
    std::vector<byte> oneVec = {0x01};
    tlv->addChild(std::make_shared<TLV>(static_cast<UINT8>(0x1), oneVec));
    int seqNrKeep;
    {
        CriticalSectionGuard lock(csResponses);
        if (seqNr == (std::numeric_limits<int>::max)()) seqNr = 1;
        seqNrKeep = seqNr++;
    }
    // The reference TLV constructors accept primitive values by reference.
    int sequence = seqNrKeep;
    tlv->addChild(std::make_shared<TLV>(static_cast<UINT8>(0x2), sequence));
    {
        CriticalSectionGuard lock(csResponses);
        HANDLE event = CreateEventW(nullptr, FALSE, FALSE, nullptr);
        if (!event) { requestStop(); return {}; }
        try {
            if (!signals.emplace(seqNrKeep, event).second) {
                CloseHandle(event);
                requestStop();
                return {};
            }
        } catch (...) {
            CloseHandle(event);
            requestStop();
            return {};
        }
    }
    if (!putData(tlv->genBytes())) requestStop();
    return waitForResponseData(seqNrKeep);
}

std::vector<byte> CommunicationNamedPipes::getMetadata()
{
    return sendRequestAndWait(0x21);
}

std::vector<byte> CommunicationNamedPipes::getDataToSend()
{
    return sendRequestAndWait(0x22);
}

bool CommunicationNamedPipes::newDataFromC2(const std::vector<byte>& data)
{
    if (!active.load()) return false;
    TLVPtr tlv = std::make_shared<TLV>(static_cast<UINT8>(0x23), std::vector<byte>(data));
    return putData(tlv->genBytes());
}

std::vector<byte> CommunicationNamedPipes::waitForResponseData(int id)
{
    HANDLE event = nullptr;
    {
        CriticalSectionGuard lock(csResponses);
        auto signal = signals.find(id);
        if (signal == signals.end()) return {};
        event = signal->second;
    }
    HANDLE events[] = {event, shutdownEvent};
    // A result request may remain outstanding while the agent is idle. Pipe
    // shutdown is the cancellation signal; a fixed timeout drops live agents.
    const DWORD wait = WaitForMultipleObjects(2, events, FALSE, INFINITE);
    CriticalSectionGuard lock(csResponses);
    CloseHandle(event);
    signals.erase(id);
    auto response = responses.find(id);
    if (wait != WAIT_OBJECT_0 || response == responses.end()) {
        responses.erase(id);
        requestStop();
        return {};
    }
    TLVPtr tlv = response->second;
    responses.erase(response);
    TLVPtr child = tlv->getChild(0x4);
    if (!child && tlv->getType() == 0x22) {
        // An idle result poll can have no data child. Keep polling for a later
        // result instead of leaving this request unanswered forever.
        return {};
    }
    if (!child || child->isParent()) {
        requestStop();
        return {};
    }
    return child->getBytes();
}
