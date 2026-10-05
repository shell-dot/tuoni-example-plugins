#include <winsock2.h>
#include <ws2tcpip.h>
#include "../exec-unit-utils/CommunicationNamedPipes.h"

#include <algorithm>
#include <condition_variable>
#include <cstdint>
#include <memory>
#include <mutex>
#include <stdexcept>
#include <thread>

namespace {
using Bytes = std::vector<byte>;
const std::uint32_t maxFrameBytes = 64u * 1024u * 1024u;

// These lengths belong to the example TCP application protocol, not agent IPC.
std::uint32_t readU32(const byte* value) {
    return std::uint32_t(value[0]) | (std::uint32_t(value[1]) << 8) |
        (std::uint32_t(value[2]) << 16) | (std::uint32_t(value[3]) << 24);
}
void appendU32(Bytes& bytes, std::uint32_t value) {
    for (unsigned shift = 0; shift != 32; shift += 8)
        bytes.push_back(static_cast<byte>(value >> shift));
}

class Winsock {
public:
    Winsock() {
        WSADATA data = {};
        if (WSAStartup(MAKEWORD(2, 2), &data) != 0)
            throw std::runtime_error("Unable to initialize Winsock");
    }
    ~Winsock() { WSACleanup(); }
    Winsock(const Winsock&) = delete;
    Winsock& operator=(const Winsock&) = delete;
};


bool waitWritable(SOCKET socket, CommunicationNamedPipes& pipe, ULONGLONG deadline) {
    while (pipe.isConnected() && GetTickCount64() < deadline) {
        fd_set writes, errors;
        FD_ZERO(&writes);
        FD_ZERO(&errors);
        FD_SET(socket, &writes);
        FD_SET(socket, &errors);
        timeval timeout = {0, 100000};
        const int ready = select(0, nullptr, &writes, &errors, &timeout);
        if (ready == SOCKET_ERROR || FD_ISSET(socket, &errors)) return false;
        if (ready > 0) return true;
    }
    return false;
}

bool connectTcp(SocketHandle& socket, CommunicationNamedPipes& pipe, const std::string& host, const std::string& port) {
    addrinfo hints = {};
    hints.ai_family = AF_UNSPEC;
    hints.ai_socktype = SOCK_STREAM;
    hints.ai_protocol = IPPROTO_TCP;
    addrinfo* raw = nullptr;
    if (getaddrinfo(host.c_str(), port.c_str(), &hints, &raw) != 0) return false;
    std::unique_ptr<addrinfo, decltype(&freeaddrinfo)> addresses(raw, &freeaddrinfo);
    const ULONGLONG deadline = GetTickCount64() + 10000;
    for (addrinfo* address = raw; address && pipe.isConnected(); address = address->ai_next) {
        socket.reset(::socket(address->ai_family, address->ai_socktype, address->ai_protocol));
        if (socket.get() == INVALID_SOCKET) continue;
        u_long nonblocking = 1;
        if (ioctlsocket(socket.get(), FIONBIO, &nonblocking) != 0) continue;
        const int result = ::connect(socket.get(), address->ai_addr, static_cast<int>(address->ai_addrlen));
        if (result == SOCKET_ERROR) {
            if (WSAGetLastError() != WSAEWOULDBLOCK || !waitWritable(socket.get(), pipe, deadline)) continue;
            int error = 0;
            int length = sizeof(error);
            if (getsockopt(socket.get(), SOL_SOCKET, SO_ERROR, reinterpret_cast<char*>(&error), &length) != 0 || error != 0)
                continue;
        }
        const BOOL enabled = TRUE;
        setsockopt(socket.get(), SOL_SOCKET, SO_KEEPALIVE,
            reinterpret_cast<const char*>(&enabled), sizeof(enabled));
        return true;
    }
    socket.reset();
    return false;
}

bool sendAll(SOCKET socket, CommunicationNamedPipes& pipe, const Bytes& bytes, ULONGLONG deadline) {
    size_t offset = 0;
    while (offset < bytes.size()) {
        if (!waitWritable(socket, pipe, deadline)) return false;
        const int sent = ::send(socket, reinterpret_cast<const char*>(bytes.data() + offset),
            static_cast<int>(std::min<size_t>(65536, bytes.size() - offset)), 0);
        if (sent == SOCKET_ERROR && WSAGetLastError() == WSAEWOULDBLOCK) continue;
        if (sent <= 0) return false;
        offset += static_cast<size_t>(sent);
    }
    return true;
}

bool sendFrame(SOCKET socket, CommunicationNamedPipes& pipe, const Bytes& metadata, const Bytes& data) {
    if (metadata.empty() || metadata.size() > maxFrameBytes || data.size() > maxFrameBytes)
        throw std::runtime_error("Invalid TCP frame size");
    // This repository's Java handler always expects both lengths, even registration.
    Bytes frame;
    frame.reserve(8 + metadata.size() + data.size());
    appendU32(frame, static_cast<uint32_t>(metadata.size()));
    frame.insert(frame.end(), metadata.begin(), metadata.end());
    appendU32(frame, static_cast<uint32_t>(data.size()));
    frame.insert(frame.end(), data.begin(), data.end());
    return sendAll(socket, pipe, frame, GetTickCount64() + 10000);
}

// Keep the potentially blocking pipe request off the TCP reader. One queued
// response bounds memory use and survives a failed TCP session for retry.
class Sender {
public:
    explicit Sender(CommunicationNamedPipes& pipe) : pipe_(pipe), worker_(&Sender::run, this) {}
    ~Sender() {
        pipe_.close(); // Wake a pending pipe response before joining the worker.
        ready_.notify_all();
        worker_.join();
    }
    Sender(const Sender&) = delete;
    Sender& operator=(const Sender&) = delete;

    bool flush(SOCKET socket) {
        std::unique_lock<std::mutex> lock(mutex_);
        if (!occupied_) return true;
        if (!sendFrame(socket, pipe_, metadata_, data_)) return false;
        metadata_.clear();
        data_.clear();
        occupied_ = false;
        lock.unlock();
        ready_.notify_one();
        return true;
    }

private:
    void run() noexcept {
        try {
            while (pipe_.isConnected()) {
                Bytes data = pipe_.getDataToSend();
                if (!pipe_.isConnected()) break;
                if (data.empty()) {
                    Sleep(100);
                    continue;
                }
                Bytes metadata = pipe_.getMetadata();
                if (!pipe_.isConnected()) break;
                if (metadata.empty()) {
                    pipe_.signalStop();
                    break;
                }
                std::unique_lock<std::mutex> lock(mutex_);
                ready_.wait(lock, [this] { return !occupied_ || !pipe_.isConnected(); });
                if (!pipe_.isConnected()) break;
                metadata_ = std::move(metadata);
                data_ = std::move(data);
                occupied_ = true;
            }
        } catch (...) {
            pipe_.signalStop();
        }
    }

    CommunicationNamedPipes& pipe_;
    std::mutex mutex_;
    std::condition_variable ready_;
    Bytes metadata_;
    Bytes data_;
    bool occupied_ = false;
    std::thread worker_;
};

bool receiveFrames(SOCKET socket, CommunicationNamedPipes& listener, Bytes& buffer) {
    // Limit work per turn so continuous inbound traffic cannot starve the sender.
    for (unsigned step = 0; step < 64; ++step) {
        size_t target = 4;
        if (buffer.size() >= 4) {
            const uint32_t length = readU32(buffer.data());
            if (length > maxFrameBytes - 5) return false; // Must also fit the IPC leaf.
            target += length;
            if (buffer.size() == target) {
                if (!listener.newDataFromC2(Bytes(buffer.begin() + 4, buffer.end())))
                    return false;
                buffer.clear();
                continue;
            }
        }
        uint8_t bytes[16384];
        const int count = recv(socket, reinterpret_cast<char*>(bytes),
            static_cast<int>(std::min<size_t>(sizeof(bytes), target - buffer.size())), 0);
        if (count == SOCKET_ERROR && WSAGetLastError() == WSAEWOULDBLOCK) return true;
        if (count <= 0) return false;
        buffer.insert(buffer.end(), bytes, bytes + count);
    }
    return true;
}

void waitForReconnect(CommunicationNamedPipes& pipe) {
    const ULONGLONG deadline = GetTickCount64() + 5000;
    while (pipe.isConnected() && GetTickCount64() < deadline) {
        Sleep(100);
    }
}

void serve(CommunicationNamedPipes& pipe, const std::string& host, const std::string& port) {
    Sender sender(pipe);
    while (pipe.isConnected()) {
        {
            SocketHandle socket;
            if (connectTcp(socket, pipe, host, port)
                && sendFrame(socket.get(), pipe, pipe.getMetadata(), Bytes())) {
                Bytes input;
                while (pipe.isConnected() && receiveFrames(socket.get(), pipe, input)) {
                    if (!sender.flush(socket.get())) break;
                    Sleep(100);
                }
            }
        } // Close the socket before waiting or returning to the loader.
        waitForReconnect(pipe);
    }
}
}

extern "C" __declspec(dllexport) void __cdecl start(const char* pipeName) {
    try {
        if (!pipeName || !*pipeName) return;
        Winsock winsock;
        CommunicationNamedPipes pipe(pipeName, {});
        const Bytes configuration = pipe.connect();
        if (!pipe.isConnected()) return;
        const std::string address(configuration.begin(), configuration.end());
        const size_t separator = address.rfind(':');
        if (separator == std::string::npos || separator == 0 || separator + 1 == address.size())
            throw std::invalid_argument("Expected host:port configuration");
        const std::string host = address.substr(0, separator);
        const std::string port = address.substr(separator + 1);
        unsigned numericPort = 0;
        for (char digit : port) {
            if (digit < '0' || digit > '9' || numericPort > 6553)
                throw std::invalid_argument("Invalid TCP port");
            numericPort = numericPort * 10 + static_cast<unsigned>(digit - '0');
        }
        if (numericPort == 0 || numericPort > 65535 || host.find('\0') != std::string::npos)
            throw std::invalid_argument("Invalid TCP endpoint");
        serve(pipe, host, port);
    } catch (...) {
        // The copied pipe utility cancels and joins its reader before DLL return.
    }
}
