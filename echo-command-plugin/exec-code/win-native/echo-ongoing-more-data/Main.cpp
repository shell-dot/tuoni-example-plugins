#include "../exec-unit-utils/CommunicationNamedPipesCommand.h"

#include <cstdint>
#include <deque>
#include <mutex>
#include <string>
#include <vector>

using Bytes = std::vector<std::uint8_t>;

struct InputState {
    std::mutex lock;
    std::deque<Bytes> updates;
    std::size_t queuedBytes = 0;
    bool stopped = false;
    bool overflowed = false;
};

static void recordUpdate(InputState& input, const Bytes& data) {
    std::lock_guard<std::mutex> guard(input.lock);
    if (input.stopped) return;
    const std::size_t maxBytes = 64u * 1024u * 1024u;
    if (input.updates.size() >= 64 || data.size() > maxBytes - input.queuedBytes) {
        input.overflowed = true;
        input.stopped = true;
        return;
    }
    input.updates.push_back(data);
    input.queuedBytes += data.size();
}

static bool stopInput(InputState& input) {
    std::lock_guard<std::mutex> guard(input.lock);
    input.stopped = true;
    return input.overflowed;
}

static bool takeUpdate(InputState& input, Bytes& data, bool& stopped) {
    std::lock_guard<std::mutex> guard(input.lock);
    if (input.updates.empty()) {
        stopped = input.stopped;
        return false;
    }
    data.swap(input.updates.front());
    input.queuedBytes -= data.size();
    input.updates.pop_front();
    return true;
}

static bool sendText(ExecUnitUtils::CommunicationNamedPipesCommand& pipe,
    const std::string& text) {
    return pipe.sendResult(Bytes(text.begin(), text.end()));
}

static bool executeCommand(ExecUnitUtils::CommunicationNamedPipesCommand& pipe,
    const Bytes& configuration, InputState& input) {
    if (!pipe.sendConf_ongoingResult() || !pipe.sendConf_stoppable(10000)) return false;
    if (!sendText(pipe, "Initial data: " +
        std::string(configuration.begin(), configuration.end()) + "\n")) return false;

    while (pipe.isConnected()) {
        Bytes update;
        bool stopped = false;
        if (!takeUpdate(input, update, stopped)) {
            if (stopped) return true;
            Sleep(25);
            continue;
        }
        if (update.empty() || (update.size() == 1 && update[0] == 0)) return true;
        if (!sendText(pipe, "New data: " +
            std::string(update.begin(), update.end()) + "\n")) return false;
    }
    return false;
}

extern "C" __declspec(dllexport) void __cdecl start(const char* pipeName) {
    if (!pipeName || !*pipeName) return;
    InputState input; // The pipe must close and join its reader before this state is destroyed.
    auto options = ExecUnitUtils::CommunicationNamedPipesOptions::structuredCommand();
    options.maxInboundFrameBytes = 64u * 1024u * 1024u;
    ExecUnitUtils::CommunicationNamedPipesCommand pipe(pipeName,
        [&input](const Bytes& data) { recordUpdate(input, data); },
        [&input]() { stopInput(input); }, options);
    Bytes configuration;
    if (!pipe.TryConnect(configuration)) return;

    bool success = false;
    success = executeCommand(pipe, configuration, input);
    const bool overflowed = stopInput(input);
    if (overflowed) {
        success = false;
        if (pipe.isConnected()) {
            const std::string error = "Command update queue exceeded its limit";
            if (!pipe.sendError(Bytes(error.begin(), error.end()))) return;
        }
    }
    if (!pipe.isConnected()) return;
    const bool completed = success ? pipe.sendReturnSuccess() : pipe.sendReturnFailed();
    if (!completed) return;
}
