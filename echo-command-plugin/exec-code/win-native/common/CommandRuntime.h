#pragma once
#include "../exec-unit-utils/CommunicationNamedPipesCommand.h"

#include <deque>
#include <stdexcept>
#include <utility>

namespace commandexample {
using Bytes = std::vector<std::uint8_t>;
const std::size_t maxFrameBytes = 64u * 1024u * 1024u;

inline Bytes textBytes(const std::string& text) { return Bytes(text.begin(), text.end()); }
inline void requireSend(bool sent) {
    if (!sent) throw std::runtime_error("Agent pipe write failed");
}

// Callbacks only record input. The invocation thread owns command behavior/output.
class CommandInput {
public:
    enum class State { idle, update, stopped };
    std::atomic<bool> stopped{false};
    void push(const Bytes& data) {
        std::lock_guard<std::mutex> lock(mutex_);
        if (stopped.load()) return;
        if (updates_.size() >= 64 || data.size() > maxFrameBytes - queuedBytes_)
            throw std::runtime_error("Command update queue exceeded its limit");
        updates_.push_back(data);
        queuedBytes_ += data.size();
    }
    void stop() {
        std::lock_guard<std::mutex> lock(mutex_);
        stopped.store(true);
    }
    State next(Bytes& data) {
        std::lock_guard<std::mutex> lock(mutex_);
        // Updates accepted before stop retain their wire order. Decide whether
        // input is exhausted under the same lock used by both callbacks.
        if (updates_.empty()) return stopped.load() ? State::stopped : State::idle;
        data = std::move(updates_.front());
        queuedBytes_ -= data.size();
        updates_.pop_front();
        return State::update;
    }
private:
    std::mutex mutex_;
    std::deque<Bytes> updates_;
    std::size_t queuedBytes_ = 0;
};

// Expose connection state without modifying the vendored transport or its framing.
class CommandChannel final : public ExecUnitUtils::CommunicationNamedPipesCommand {
public:
    CommandChannel(const char* name, CommandInput& input)
        : CommunicationNamedPipesCommand(name,
            [&input](const Bytes& data) { input.push(data); },
            [&input]() { input.stop(); }, options()) {}
    bool connected() const { return _active.load() && !_cancelRequested.load(); }
private:
    static ExecUnitUtils::CommunicationNamedPipesOptions options() {
        auto result = ExecUnitUtils::CommunicationNamedPipesOptions::structuredCommand();
        result.maxInboundFrameBytes = static_cast<std::uint32_t>(maxFrameBytes);
        return result;
    }
};

template <typename Execute>
void runCommand(const char* name, Execute execute) noexcept {
    try {
        if (!name || !*name) return;
        CommandInput input; // Must outlive callbacks and the pipe's joined reader.
        CommandChannel pipe(name, input);
        bool succeeded = false;
        try {
            Bytes configuration;
            if (!pipe.TryConnect(configuration)) return;
            execute(pipe, configuration, input);
            succeeded = true;
        } catch (const std::exception& error) {
            try { if (pipe.connected()) requireSend(pipe.sendError(textBytes(error.what()))); }
            catch (...) { }
        } catch (...) { }
        // One terminal owner. A failed write is never retried on a partial channel.
        if (pipe.connected())
            requireSend(succeeded ? pipe.sendReturnSuccess() : pipe.sendReturnFailed());
        pipe.close(); // Cancels I/O and joins the reader before input is destroyed.
    } catch (...) { }
}
} // namespace commandexample
