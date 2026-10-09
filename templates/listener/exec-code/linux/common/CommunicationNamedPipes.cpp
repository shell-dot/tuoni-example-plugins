#include "CommunicationNamedPipes.h"
#include <cerrno>
#include <poll.h>
#include <pthread.h>
#include <signal.h>
#include <stdexcept>

namespace {
    bool readAll(int fd, void* data, size_t length, const std::atomic<bool>& active) {
        uint8_t* cursor = static_cast<uint8_t*>(data);
        while (length != 0 && active) {
            const ssize_t count = read(fd, cursor, length);
            if (count > 0) {
                cursor += count;
                length -= static_cast<size_t>(count);
                continue;
            }
            if (count < 0 && errno == EINTR)
                continue;
            if (count < 0 && (errno == EAGAIN || errno == EWOULDBLOCK)) {
                pollfd descriptor = {fd, POLLIN, 0};
                const int ready = poll(&descriptor, 1, 100);
                if (ready < 0 && errno != EINTR)
                    return false;
                continue;
            }
            return false; // EOF or unrecoverable read failure.
        }
        return length == 0;
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

void CommunicationNamedPipes::setCallback(CallbackFunc* callbackIn)
{
    callback = callbackIn;
}

std::vector<uint8_t> CommunicationNamedPipes::connect()
{
    pipe_read = open(pipeNameRead.c_str(), O_RDONLY);
    if (pipe_read == -1)
    {
        throw std::runtime_error("Unable to open the listener read FIFO.");
    }

    pipe_write = open(pipeNameWrite.c_str(), O_WRONLY);
    if (pipe_write == -1)
    {
        close();
        throw std::runtime_error("Unable to open the listener write FIFO.");
    }

    // Nonblocking reads let shutdown cancel the owned reader without relying on
    // closing a descriptor from another thread to interrupt a blocking syscall.
    const int flags = fcntl(pipe_read, F_GETFL);
    if (flags == -1 || fcntl(pipe_read, F_SETFL, flags | O_NONBLOCK) == -1
        || !writeAll(pipe_write, "\x00", 1)) {
        close();
        throw std::runtime_error("Unable to initialize the listener FIFO connection.");
    }

    active = true;
    auto data = getData();
    uint32_t payloadLength = 0;
    if (data.size() >= 5)
        std::memcpy(&payloadLength, data.data() + 1, sizeof(payloadLength));
    TLV tlv;
    if (data.size() < 5 || (data[0] & TLV_PARENT_TYPE_FLAG) != 0
        || payloadLength != data.size() - 5 || !tlv.load(data))
    {
        close();
        throw std::runtime_error("Unable to receive a complete listener configuration frame.");
    }

    listen_thread = std::thread(&CommunicationNamedPipes::listenForMessages, this);
    return tlv.getValue();
}

void CommunicationNamedPipes::listenForMessages()
{
    try {
        while (active) {
            auto data = getData();
            if (data.empty())
                break;

            std::shared_ptr<TLV> tlv(new TLV());
            if (!tlv->load(data))
                continue;

            if (tlv->getType() == 0x20 && callback) {
                auto child = tlv->getChild(0x4);
                if (child)
                    callback(child->getValue());
                continue;
            }
            if ((tlv->getType() == 0x21 || tlv->getType() == 0x22)
                && tlv->getChild(0x2) != nullptr) {
                uint32_t sequence = 0;
                if (!tlv->getChild(0x2)->getUInt32(sequence))
                    continue;
                const int id = static_cast<int>(sequence);
                std::unique_lock<std::mutex> lock(mtx);
                responses[id] = tlv;
                if (signal.count(id))
                    sem_post(&signal[id]);
            }
        }
    } catch (...) {
        // Worker exceptions must never escape into the agent host.
    }
    active = false;
}

std::vector<uint8_t> CommunicationNamedPipes::getData()
{
    if (!active)
        return {};

    uint32_t len = 0;
    if (!readAll(pipe_read, &len, sizeof(len), active) || len < 5 || len > 16 * 1024 * 1024)
    {
        active = false;
        return {};
    }

    std::vector<uint8_t> buffer(len);
    if (!readAll(pipe_read, buffer.data(), len, active)) {
        active = false;
        return {};
    }
    return buffer;
}

bool CommunicationNamedPipes::putData(const std::vector<uint8_t> &data)
{
    std::lock_guard<std::mutex> lock(mtx);
    if (!active)
        return false;

    if (data.size() > 16 * 1024 * 1024)
        return false;
    uint32_t len = static_cast<uint32_t>(data.size());
    if (!writeAll(pipe_write, &len, sizeof(len)) || !writeAll(pipe_write, data.data(), len))
    {
        active = false;
        return false;
    }

    return true;
}

void CommunicationNamedPipes::close()
{
    active = false;
    waitForDisconnect();
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

void CommunicationNamedPipes::waitForDisconnect()
{
    if (listen_thread.joinable())
    {
        listen_thread.join();
    }
}


void CommunicationNamedPipes::newDataFromC2(std::vector<uint8_t> data)
{
    if (!active)
        return;

    TLV tlv(0x23, data);
    putData(tlv.genBytes());
}

std::vector<uint8_t> CommunicationNamedPipes::getMetadata()
{
    if (!active)
        return {};

    TLV tlv(0x21);
    tlv.addChild(std::shared_ptr<TLV>(new TLV(0x1, std::vector<uint8_t>{0x1})));
    int seqNrKeep = seqNr++;
    tlv.addChild(std::shared_ptr<TLV>(new TLV(0x2, &seqNrKeep, sizeof(seqNrKeep))));
    putData(tlv.genBytes());
    return waitForResponseData(seqNrKeep);
}

std::vector<uint8_t> CommunicationNamedPipes::getDataToSend()
{
    if (!active)
        return {};

    TLV tlv(0x22);
    tlv.addChild(std::shared_ptr<TLV>(new TLV(0x1, std::vector<uint8_t>{0x1})));
    int seqNrKeep = seqNr++;
    tlv.addChild(std::shared_ptr<TLV>(new TLV(0x2, &seqNrKeep, sizeof(seqNrKeep))));
    putData(tlv.genBytes());
    return waitForResponseData(seqNrKeep);
}

std::vector<uint8_t> CommunicationNamedPipes::waitForResponseData(int id)
{
    std::shared_ptr<TLV> tlv = NULL;
    
    {
        std::unique_lock<std::mutex> lock(mtx);
        if(responses.count(id))
        {
            tlv = responses[id];
            responses.erase(id);
        }
        else
        {
            signal[id] = sem_t();
            sem_init(&signal[id], 0, 0);
        }
    }

    if(!tlv.get())
    {
        sem_wait(&signal[id]);
        {
            std::unique_lock<std::mutex> lock(mtx);
            tlv = responses[id];
            sem_destroy(&signal[id]);
            responses.erase(id);
            signal.erase(id);
        }
    }

    if (tlv->getChild(0x4) == nullptr)
    {
        return {};
    }
    return tlv->getChild(0x4)->getValue();
}
