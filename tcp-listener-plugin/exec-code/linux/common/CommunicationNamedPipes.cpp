#include "CommunicationNamedPipes.h"

#include <cerrno>
#include <fcntl.h>
#include <poll.h>
#include <pthread.h>
#include <signal.h>
#include <unistd.h>

namespace {
constexpr size_t maxFrameBytes = 64u * 1024u * 1024u;

bool writeAll(int fd, const void* data, size_t length, const std::atomic<bool>& active) {
    // Keep SIGPIPE local to this thread; a closed FIFO must not kill the host.
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
    while (length != 0 && active.load()) {
        const ssize_t count = write(fd, cursor, length);
        if (count < 0 && errno == EINTR)
            continue;
        if (count < 0 && (errno == EAGAIN || errno == EWOULDBLOCK)) {
            pollfd descriptor = {fd, POLLOUT, 0};
            const int ready = poll(&descriptor, 1, 100);
            if (ready < 0 && errno != EINTR) {
                success = false;
                break;
            }
            continue;
        }
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
    return success && length == 0;
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
        return {};

    pipe_write = open(pipeNameWrite.c_str(), O_WRONLY);
    if (pipe_write == -1) {
        close();
        return {};
    }

    const int readFlags = fcntl(pipe_read, F_GETFL);
    const int writeFlags = fcntl(pipe_write, F_GETFL);
    if (readFlags == -1 || writeFlags == -1 ||
        fcntl(pipe_read, F_SETFL, readFlags | O_NONBLOCK) == -1 ||
        fcntl(pipe_write, F_SETFL, writeFlags | O_NONBLOCK) == -1) {
        close();
        return {};
    }

    active.store(true);
    if (!writeAll(pipe_write, "\x00", 1, active)) {
        close();
        return {};
    }

    const std::vector<uint8_t> data = getData();
    TLV tlv;
    if (!active.load() || !tlv.load(data)) {
        close();
        return {};
    }

    listen_thread = std::thread(&CommunicationNamedPipes::listenForMessages, this);
    return tlv.getValue();
}

void CommunicationNamedPipes::listenForMessages()
{
    try {
        while (active.load()) {
            const std::vector<uint8_t> data = getData();
            if (data.empty())
                break;

            std::shared_ptr<TLV> tlv(new TLV());
            if (!tlv->load(data))
                continue;
            if (tlv->getType() == 0x20 && callback) {
                const std::shared_ptr<TLV> child = tlv->getChild(0x4);
                if (child)
                    callback(child->getValue());
                continue;
            }
            if ((tlv->getType() == 0x21 || tlv->getType() == 0x22) &&
                tlv->getChild(0x2) != nullptr) {
                const int id = tlv->getChild(0x2)->getUInt32();
                std::lock_guard<std::mutex> lock(mtx);
                responses[id] = tlv;
                responsesReady.notify_all();
            }
        }
    } catch (...) {
        // Worker exceptions must not escape into the host.
    }
    active.store(false);
    responsesReady.notify_all();
}

bool CommunicationNamedPipes::readExact(void* buffer, size_t length)
{
    uint8_t* cursor = static_cast<uint8_t*>(buffer);
    while (length != 0 && active.load()) {
        pollfd descriptor = {pipe_read, POLLIN, 0};
        const int ready = poll(&descriptor, 1, 100);
        if (ready == 0 || (ready < 0 && errno == EINTR))
            continue;
        if (ready < 0)
            return false;
        const ssize_t count = read(pipe_read, cursor, length);
        if (count < 0 && (errno == EINTR || errno == EAGAIN || errno == EWOULDBLOCK))
            continue;
        if (count <= 0)
            return false;
        cursor += count;
        length -= static_cast<size_t>(count);
    }
    return length == 0;
}

std::vector<uint8_t> CommunicationNamedPipes::getData()
{
    if (!active.load())
        return {};

    uint32_t length = 0;
    if (!readExact(&length, sizeof(length)) || length > maxFrameBytes) {
        active.store(false);
        responsesReady.notify_all();
        return {};
    }

    std::vector<uint8_t> buffer(length);
    if (length != 0 && !readExact(buffer.data(), length)) {
        active.store(false);
        responsesReady.notify_all();
        return {};
    }
    return buffer;
}

bool CommunicationNamedPipes::putData(const std::vector<uint8_t>& data)
{
    std::lock_guard<std::mutex> lock(mtx);
    if (!active.load() || data.size() > maxFrameBytes)
        return false;

    const uint32_t length = static_cast<uint32_t>(data.size());
    if (!writeAll(pipe_write, &length, sizeof(length), active) ||
        !writeAll(pipe_write, data.data(), length, active)) {
        active.store(false);
        responsesReady.notify_all();
        return false;
    }
    return true;
}

void CommunicationNamedPipes::close()
{
    requestStop();
    if (listen_thread.joinable())
        listen_thread.join();
    if (pipe_read != -1) {
        ::close(pipe_read);
        pipe_read = -1;
    }
    if (pipe_write != -1) {
        ::close(pipe_write);
        pipe_write = -1;
    }
}

void CommunicationNamedPipes::requestStop()
{
    active.store(false);
    responsesReady.notify_all();
}

void CommunicationNamedPipes::newDataFromC2(std::vector<uint8_t> data)
{
    if (!active.load())
        return;
    TLV tlv(0x23, data);
    putData(tlv.genBytes());
}

std::vector<uint8_t> CommunicationNamedPipes::getMetadata()
{
    if (!active.load())
        return {};
    TLV tlv(0x21);
    tlv.addChild(std::shared_ptr<TLV>(new TLV(0x1, std::vector<uint8_t>{0x1})));
    int id = seqNr++;
    tlv.addChild(std::shared_ptr<TLV>(new TLV(0x2, &id, sizeof(id))));
    if (!putData(tlv.genBytes()))
        return {};
    return waitForResponseData(id);
}

std::vector<uint8_t> CommunicationNamedPipes::getDataToSend()
{
    if (!active.load())
        return {};
    TLV tlv(0x22);
    tlv.addChild(std::shared_ptr<TLV>(new TLV(0x1, std::vector<uint8_t>{0x1})));
    int id = seqNr++;
    tlv.addChild(std::shared_ptr<TLV>(new TLV(0x2, &id, sizeof(id))));
    if (!putData(tlv.genBytes()))
        return {};
    return waitForResponseData(id);
}

std::vector<uint8_t> CommunicationNamedPipes::waitForResponseData(int id)
{
    std::unique_lock<std::mutex> lock(mtx);
    responsesReady.wait(lock, [this, id] {
        return !active.load() || responses.find(id) != responses.end();
    });
    const auto response = responses.find(id);
    if (response == responses.end())
        return {};
    const std::shared_ptr<TLV> tlv = response->second;
    responses.erase(response);
    lock.unlock();
    const std::shared_ptr<TLV> child = tlv->getChild(0x4);
    return child ? child->getValue() : std::vector<uint8_t>{};
}
