#include "CommunicationNamedPipes.h"

#include <atomic>
#include <cerrno>
#include <chrono>
#include <condition_variable>
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <functional>
#include <fcntl.h>
#include <mutex>
#include <poll.h>
#include <string>
#include <thread>
#include <vector>

#include <netdb.h>
#include <sys/socket.h>
#include <unistd.h>

namespace {
constexpr uint32_t maxFrameBytes = 64u * 1024u * 1024u;
constexpr int reconnectSeconds = 5;

bool readAll(int fd, void* output, size_t length, const CommunicationNamedPipes& pipe) {
    uint8_t* bytes = static_cast<uint8_t*>(output);
    while (length != 0 && pipe.isConnected()) {
        pollfd descriptor = {fd, POLLIN, 0};
        const int ready = ::poll(&descriptor, 1, 100);
        if (ready == 0 || (ready < 0 && errno == EINTR))
            continue;
        if (ready < 0)
            return false;
        const ssize_t count = ::recv(fd, bytes, length, MSG_DONTWAIT);
        if (count < 0 && (errno == EINTR || errno == EAGAIN || errno == EWOULDBLOCK))
            continue;
        if (count <= 0)
            return false;
        bytes += count;
        length -= static_cast<size_t>(count);
    }
    return length == 0;
}

bool writeAll(int fd, const void* input, size_t length,
              const std::atomic<bool>* stopping = nullptr,
              const CommunicationNamedPipes* pipe = nullptr) {
    const uint8_t* bytes = static_cast<const uint8_t*>(input);
    const auto deadline = std::chrono::steady_clock::now() + std::chrono::seconds(10);
    while (length != 0) {
        if ((stopping && stopping->load()) || (pipe && !pipe->isConnected()) ||
            std::chrono::steady_clock::now() >= deadline)
            return false;
        const ssize_t count = ::send(fd, bytes, length, MSG_DONTWAIT | MSG_NOSIGNAL);
        if (count < 0 && errno == EINTR)
            continue;
        if (count < 0 && (errno == EAGAIN || errno == EWOULDBLOCK)) {
            pollfd descriptor = {fd, POLLOUT, 0};
            const int ready = ::poll(&descriptor, 1, 100);
            if (ready < 0 && errno != EINTR)
                return false;
            continue;
        }
        if (count <= 0)
            return false;
        bytes += count;
        length -= static_cast<size_t>(count);
    }
    return true;
}

bool writeLength(int fd, uint32_t value, const std::atomic<bool>* stopping = nullptr,
                 const CommunicationNamedPipes* pipe = nullptr) {
    const uint8_t bytes[] = {
        static_cast<uint8_t>(value), static_cast<uint8_t>(value >> 8),
        static_cast<uint8_t>(value >> 16), static_cast<uint8_t>(value >> 24)};
    return writeAll(fd, bytes, sizeof(bytes), stopping, pipe);
}

bool readLength(int fd, uint32_t& value, const CommunicationNamedPipes& pipe) {
    uint8_t bytes[4];
    if (!readAll(fd, bytes, sizeof(bytes), pipe))
        return false;
    value = static_cast<uint32_t>(bytes[0]) |
            (static_cast<uint32_t>(bytes[1]) << 8) |
            (static_cast<uint32_t>(bytes[2]) << 16) |
            (static_cast<uint32_t>(bytes[3]) << 24);
    return value <= maxFrameBytes;
}

bool writeFrame(int fd, const std::vector<uint8_t>& metadata,
                const std::vector<uint8_t>& data,
                const std::atomic<bool>* stopping = nullptr,
                const CommunicationNamedPipes* pipe = nullptr) {
    return metadata.size() <= maxFrameBytes && data.size() <= maxFrameBytes &&
           writeLength(fd, static_cast<uint32_t>(metadata.size()), stopping, pipe) &&
           writeAll(fd, metadata.data(), metadata.size(), stopping, pipe) &&
           writeLength(fd, static_cast<uint32_t>(data.size()), stopping, pipe) &&
           writeAll(fd, data.data(), data.size(), stopping, pipe);
}

int connectTcp(const std::string& host, const std::string& port,
               const CommunicationNamedPipes& pipe) {
    addrinfo hints = {};
    hints.ai_family = AF_UNSPEC;
    hints.ai_socktype = SOCK_STREAM;
    addrinfo* addresses = nullptr;
    if (::getaddrinfo(host.c_str(), port.c_str(), &hints, &addresses) != 0)
        return -1;
    int fd = -1;
    for (addrinfo* address = addresses; address && pipe.isConnected(); address = address->ai_next) {
        fd = ::socket(address->ai_family, address->ai_socktype, address->ai_protocol);
        if (fd < 0)
            continue;
        const int flags = ::fcntl(fd, F_GETFL);
        if (flags < 0 || ::fcntl(fd, F_SETFL, flags | O_NONBLOCK) < 0) {
            ::close(fd);
            fd = -1;
            continue;
        }
        bool connected = ::connect(fd, address->ai_addr, address->ai_addrlen) == 0;
        if (!connected && errno == EINPROGRESS) {
            const auto deadline = std::chrono::steady_clock::now() + std::chrono::seconds(5);
            while (pipe.isConnected() && std::chrono::steady_clock::now() < deadline) {
                pollfd descriptor = {fd, POLLOUT, 0};
                const int ready = ::poll(&descriptor, 1, 100);
                if (ready < 0 && errno == EINTR)
                    continue;
                if (ready <= 0)
                    continue;
                int error = 0;
                socklen_t errorLength = sizeof(error);
                if (::getsockopt(fd, SOL_SOCKET, SO_ERROR, &error, &errorLength) == 0 && error == 0)
                    connected = true;
                break;
            }
        }
        if (connected && pipe.isConnected())
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
        if (stopping_.load())
            return;
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

    bool send(const std::vector<uint8_t>& metadata, const std::vector<uint8_t>& data) {
        while (!stopping_.load()) {
            std::unique_lock<std::mutex> lock(mutex_);
            changed_.wait(lock, [this] { return fd_ >= 0 || stopping_.load(); });
            if (stopping_.load())
                return false;
            if (writeFrame(fd_, metadata, data, &stopping_))
                return true;
            const int failedFd = fd_;
            fd_ = -1;
            ::shutdown(failedFd, SHUT_RDWR);
        }
        return false;
    }

    void stop() {
        stopping_.store(true);
        changed_.notify_all();
        std::lock_guard<std::mutex> lock(mutex_);
        if (fd_ >= 0)
            ::shutdown(fd_, SHUT_RDWR);
    }

private:
    std::atomic<bool> stopping_{false};
    std::mutex mutex_;
    std::condition_variable changed_;
    int fd_ = -1;
};

void sendLoop(CommunicationNamedPipes& pipe, Session& session) {
    try {
        while (pipe.isConnected()) {
            const std::vector<uint8_t> data = pipe.getDataToSend();
            if (!pipe.isConnected())
                return;
            if (data.empty()) {
                std::this_thread::sleep_for(std::chrono::milliseconds(100));
                continue;
            }
            const std::vector<uint8_t> metadata = pipe.getMetadata();
            if (!pipe.isConnected())
                return;
            if (!metadata.empty() && !session.send(metadata, data))
                return;
        }
    } catch (...) {
        pipe.requestStop();
    }
}

void serve(CommunicationNamedPipes& pipe, const std::string& host, const std::string& port) {
    Session session;
    std::thread sender(sendLoop, std::ref(pipe), std::ref(session));
    struct SenderOwner {
        CommunicationNamedPipes& pipe;
        Session& session;
        std::thread& sender;
        ~SenderOwner() {
            session.stop();
            pipe.requestStop();
            if (sender.joinable())
                sender.join();
            pipe.close();
        }
    } owner{pipe, session, sender};
    while (pipe.isConnected()) {
        const int fd = connectTcp(host, port, pipe);
        if (fd >= 0) {
            struct SocketOwner {
                Session& session;
                CommunicationNamedPipes& pipe;
                int fd;
                ~SocketOwner() {
                    if (!pipe.isConnected())
                        session.stop();
                    session.clear(fd);
                    ::close(fd);
                }
            } socket{session, pipe, fd};
            const std::vector<uint8_t> metadata = pipe.getMetadata();
            if (!metadata.empty() && writeFrame(fd, metadata, {}, nullptr, &pipe)) {
                session.set(fd);
                uint32_t length;
                while (readLength(fd, length, pipe)) {
                    std::vector<uint8_t> data(length);
                    if (!readAll(fd, data.data(), length, pipe))
                        break;
                    pipe.newDataFromC2(data);
                }
            }
        }
        for (int elapsed = 0; elapsed < reconnectSeconds * 10 && pipe.isConnected(); ++elapsed)
            std::this_thread::sleep_for(std::chrono::milliseconds(100));
    }
}
}

extern "C" void run(char* pipeNameRead, char* pipeNameWrite) {
    if (!pipeNameRead || !pipeNameWrite)
        return;
    try {
        CommunicationNamedPipes pipe(pipeNameRead, pipeNameWrite, nullptr);
        const std::vector<uint8_t> configuration = pipe.connect();
        if (!pipe.isConnected())
            return;
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
    } catch (...) {
        // Do not let an invocation failure unwind through the host entrypoint.
    }
}
