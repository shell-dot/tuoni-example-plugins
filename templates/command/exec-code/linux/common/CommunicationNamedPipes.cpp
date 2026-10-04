#include "CommunicationNamedPipes.h"

#include <fcntl.h>
#include <unistd.h>
#include <cerrno>
#include <cstring>
#include <pthread.h>
#include <signal.h>
#include <stdexcept>

namespace {
    bool readAll(int fd, void* data, size_t length) {
        uint8_t* cursor = static_cast<uint8_t*>(data);
        while (length != 0) {
            const ssize_t count = read(fd, cursor, length);
            if (count < 0 && errno == EINTR)
                continue;
            if (count <= 0)
                return false;
            cursor += count;
            length -= static_cast<size_t>(count);
        }
        return true;
    }

    bool writeAll(int fd, const void* data, size_t length) {
        // A disconnected FIFO must not terminate the agent. Mask SIGPIPE only on
        // this thread, consume a newly generated signal, and restore the host mask.
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
        throw std::runtime_error("Unable to open the command read FIFO.");
    }

    pipe_write = open(pipeNameWrite.c_str(), O_WRONLY);
    if (pipe_write == -1)
    {
        close();
        throw std::runtime_error("Unable to open the command write FIFO.");
    }

    if (!writeAll(pipe_write, "\x00", 1)) {
        close();
        throw std::runtime_error("Unable to send the command readiness byte.");
    }

    active = true;
    auto data = getData();
    // Validate the complete leaf envelope before invoking the generic TLV decoder.
    uint32_t payloadLength = 0;
    if (data.size() >= 5)
        std::memcpy(&payloadLength, data.data() + 1, sizeof(payloadLength));
    TLV tlv;
    if (data.size() < 5 || (data[0] & TLV_PARENT_TYPE_FLAG) != 0
        || payloadLength != data.size() - 5 || !tlv.load(data))
    {
        close();
        throw std::runtime_error("Unable to receive a complete command configuration frame.");
    }

    startListenerIfNeeded();
    return tlv.getValue();
}

std::vector<uint8_t> CommunicationNamedPipes::getData()
{
    if (!active)
    {
        return {};
    }

    uint32_t len = 0;
    if (!readAll(pipe_read, &len, sizeof(len)) || len < 5 || len > 16 * 1024 * 1024)
    {
        active = false;
        return {};
    }

    std::vector<uint8_t> buffer(len);
    if (!readAll(pipe_read, buffer.data(), len)) {
        active = false;
        return {};
    }
    return buffer;
}

bool CommunicationNamedPipes::putData(const std::vector<uint8_t> &data)
{
    std::lock_guard<std::mutex> lock(mtx);
    if (!active)
    {
        return false;
    }

    if (data.size() > 16 * 1024 * 1024)
        return false;
    uint32_t len = static_cast<uint32_t>(data.size());
    if (!writeAll(pipe_write, &len, sizeof(len)) || !writeAll(pipe_write, data.data(), len))
    {
        // A failed frame may be partial. No further writes may reuse this stream.
        active = false;
        return false;
    }

    return true;
}

void CommunicationNamedPipes::close()
{
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
    active = false;
}

bool CommunicationNamedPipes::sendResult(const std::vector<uint8_t> &data)
{
    if (!active)
    {
        return false;
    }
    TLV tlv(0x30, data);
    return putData(tlv.genBytes());
}

bool CommunicationNamedPipes::sendError(const std::vector<uint8_t> &data)
{
    if (!active)
    {
        return false;
    }
    TLV tlv(0x32, data);
    return putData(tlv.genBytes());
}

bool CommunicationNamedPipes::sendReturnSuccess()
{
    if (!active)
    {
        return false;
    }
    TLV tlv(0x33);
    return putData(tlv.genBytes());
}

bool CommunicationNamedPipes::sendReturnFailed()
{
    if (!active)
    {
        return false;
    }
    TLV tlv(0x34);
    return putData(tlv.genBytes());
}

void CommunicationNamedPipes::sendConf_ongoingResult()
{
    if (!active)
    {
        return;
    }
    TLV tlv(0x31);
    tlv.addChild(std::shared_ptr<TLV>(new TLV(0x1, (PVOID)"\x01", 1)));
    putData(tlv.genBytes());
}

void CommunicationNamedPipes::sendConf_relayInBlocks()
{
    if (!active)
    {
        return;
    }
    TLV tlv(0x31);
    tlv.addChild(std::shared_ptr<TLV>(new TLV(0x2, (PVOID)"\x01", 1)));
    putData(tlv.genBytes());
}

void CommunicationNamedPipes::sendConf_stoppable(uint32_t waitTime)
{
    if (!active)
    {
        return;
    }
    TLV tlv(0x31);
    tlv.addChild(std::shared_ptr<TLV>(new TLV(0x3, (PVOID)&waitTime, sizeof(waitTime))));
    putData(tlv.genBytes());
}

void CommunicationNamedPipes::setCallback(CallbackFunc* callbackIn)
{
    setCallbackNewData(callbackIn);
}

void CommunicationNamedPipes::setCallbackNewData(CallbackFunc* callbackIn)
{
    callbackNewData = callbackIn;
    startListenerIfNeeded();
}

void CommunicationNamedPipes::setCallbackStop(CallbackFuncStop* callbackIn)
{
    callbackStop = callbackIn;
    startListenerIfNeeded();
}

void CommunicationNamedPipes::startListenerIfNeeded()
{
    if (!active || listenerStarted || (!callbackNewData && !callbackStop))
    {
        return;
    }

    listenerStarted = true;
    listen_thread = std::thread(&CommunicationNamedPipes::listenForMessages, this);
    listen_thread.detach();
}

void CommunicationNamedPipes::listenForMessages()
{
    while (true)
    {
        auto data = getData();
        if (data.empty())
        {
            return;
        }

        std::shared_ptr<TLV> tlv(new TLV());
        if (!tlv->load(data))
        {
            continue;
        }

        if (tlv->getType() == 0x39 && callbackNewData)
        {
            callbackNewData(tlv->getValue());
            continue;
        }
        if (tlv->getType() == 0x3F && callbackStop)
        {
            callbackStop();
            continue;
        }
    }
}
