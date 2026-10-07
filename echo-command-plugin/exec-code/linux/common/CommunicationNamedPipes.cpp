#include "CommunicationNamedPipes.h"

#include <fcntl.h>
#include <cerrno>
#include <limits>
#include <poll.h>
#include <pthread.h>
#include <signal.h>
#include <utility>
#include <unistd.h>

namespace {
bool writeAll(int fd, const void* data, size_t length) {
    sigset_t blocked, previous, pending;
    sigemptyset(&blocked);
    sigaddset(&blocked, SIGPIPE);
    if (pthread_sigmask(SIG_BLOCK, &blocked, &previous) != 0)
        return false;
    if (sigpending(&pending) != 0) {
        pthread_sigmask(SIG_SETMASK, &previous, nullptr);
        return false;
    }
    const bool alreadyPending = sigismember(&pending, SIGPIPE) == 1;
    const uint8_t* cursor = static_cast<const uint8_t*>(data);
    bool success = true;
    bool brokenPipe = false;
    while (length != 0) {
        const ssize_t count = write(fd, cursor, length);
        if (count < 0 && errno == EINTR)
            continue;
        if (count <= 0) {
            brokenPipe = count < 0 && errno == EPIPE;
            success = false;
            break;
        }
        cursor += count;
        length -= static_cast<size_t>(count);
    }
    if (brokenPipe && !alreadyPending) {
        const timespec noWait = {0, 0};
        while (sigtimedwait(&blocked, nullptr, &noWait) < 0 && errno == EINTR) { }
    }
    pthread_sigmask(SIG_SETMASK, &previous, nullptr);
    return success;
}
}

std::vector<uint8_t> CommunicationNamedPipes::connect()
{
    pipe_read = open(pipeNameRead.c_str(), O_RDONLY);
    if (pipe_read == -1)
    {
        return {};
    }

    pipe_write = open(pipeNameWrite.c_str(), O_WRONLY);
    if (pipe_write == -1)
    {
        close();
        return {};
    }

    if (!writeAll(pipe_write, "\x00", 1))
    {
        close();
        return {};
    }

    active.store(true);
    auto data = getData();
    TLV tlv;
    if (!tlv.load(data))
    {
        close();
        return {};
    }

    startListenerIfNeeded();
    return tlv.getValue();
}

std::vector<uint8_t> CommunicationNamedPipes::getData()
{
    if (!active.load())
    {
        return {};
    }

    uint32_t len = 0;
    if (!readExact(&len, sizeof(len)) || len > 64u * 1024u * 1024u)
    {
        return {};
    }

    std::vector<uint8_t> buffer(len);
    if (len != 0 && !readExact(buffer.data(), len)) return {};
    return buffer;
}

bool CommunicationNamedPipes::readExact(void* buffer, std::size_t size)
{
    std::size_t received = 0;
    while (received < size && active.load())
    {
        pollfd descriptor = {pipe_read, POLLIN, 0};
        const int ready = poll(&descriptor, 1, 100);
        if (ready == 0 || (ready < 0 && errno == EINTR)) continue;
        if (ready < 0) return false;
        const ssize_t count = read(pipe_read,
            static_cast<uint8_t*>(buffer) + received, size - received);
        if (count < 0 && errno == EINTR) continue;
        if (count <= 0) return false;
        received += static_cast<std::size_t>(count);
    }
    return received == size;
}

bool CommunicationNamedPipes::putData(const std::vector<uint8_t> &data)
{
    std::lock_guard<std::mutex> lock(mtx);
    if (!active.load() || data.size() > (std::numeric_limits<uint32_t>::max)())
    {
        return false;
    }

    uint32_t len = static_cast<uint32_t>(data.size());
    if (!writeAll(pipe_write, &len, sizeof(len)) ||
        !writeAll(pipe_write, data.data(), len))
    {
        active.store(false);
        return false;
    }

    return true;
}

void CommunicationNamedPipes::close()
{
    active.store(false);
    if (listen_thread.joinable()) listen_thread.join();
    if (pipe_read != -1)
    {
        ::close(pipe_read);
        pipe_read = -1;
    }
    if (pipe_write != -1)
    {
        ::close(pipe_write);
        pipe_write = -1;
    }
}

bool CommunicationNamedPipes::sendResult(const std::vector<uint8_t> &data)
{
    if (!active.load())
    {
        return false;
    }
    TLV tlv(0x30, data);
    return putData(tlv.genBytes());
}

bool CommunicationNamedPipes::sendError(const std::vector<uint8_t> &data)
{
    if (!active.load())
    {
        return false;
    }
    TLV tlv(0x32, data);
    return putData(tlv.genBytes());
}

bool CommunicationNamedPipes::sendReturnSuccess()
{
    if (!active.load())
    {
        return false;
    }
    TLV tlv(0x33);
    return putData(tlv.genBytes());
}

bool CommunicationNamedPipes::sendReturnFailed()
{
    if (!active.load())
    {
        return false;
    }
    TLV tlv(0x34);
    return putData(tlv.genBytes());
}

bool CommunicationNamedPipes::sendConf_ongoingResult()
{
    if (!active.load())
    {
        return false;
    }
    TLV tlv(0x31);
    tlv.addChild(std::shared_ptr<TLV>(new TLV(0x1, (PVOID)"\x01", 1)));
    return putData(tlv.genBytes());
}

bool CommunicationNamedPipes::sendConf_relayInBlocks()
{
    if (!active.load())
    {
        return false;
    }
    TLV tlv(0x31);
    tlv.addChild(std::shared_ptr<TLV>(new TLV(0x2, (PVOID)"\x01", 1)));
    return putData(tlv.genBytes());
}

bool CommunicationNamedPipes::sendConf_stoppable(uint32_t waitTime)
{
    if (!active.load())
    {
        return false;
    }
    TLV tlv(0x31);
    tlv.addChild(std::shared_ptr<TLV>(new TLV(0x3, (PVOID)&waitTime, sizeof(waitTime))));
    return putData(tlv.genBytes());
}

void CommunicationNamedPipes::setCallbackNewData(
    std::function<void(const std::vector<uint8_t>&)> callbackIn)
{
    callbackNewData = std::move(callbackIn);
    startListenerIfNeeded();
}

void CommunicationNamedPipes::setCallbackStop(std::function<void()> callbackIn)
{
    callbackStop = std::move(callbackIn);
    startListenerIfNeeded();
}

void CommunicationNamedPipes::startListenerIfNeeded()
{
    if (!active.load() || listenerStarted || (!callbackNewData && !callbackStop))
    {
        return;
    }

    listen_thread = std::thread(&CommunicationNamedPipes::listenForMessages, this);
    listenerStarted = true;
}

void CommunicationNamedPipes::listenForMessages()
{
    try
    {
        while (active.load())
        {
            auto data = getData();
            if (data.empty()) break;

            std::shared_ptr<TLV> tlv(new TLV());
            if (!tlv->load(data)) continue;

            if (tlv->getType() == 0x39 && callbackNewData)
                callbackNewData(tlv->getValue());
            else if (tlv->getType() == 0x3F && callbackStop)
                callbackStop();
        }
    }
    catch (...) { }
    active.store(false);
}
