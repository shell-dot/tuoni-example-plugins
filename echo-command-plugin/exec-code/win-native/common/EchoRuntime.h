#pragma once
#include "CommandRuntime.h"

namespace echoexample {
using namespace commandexample;

inline bool sent(bool success, std::string& error) {
    if (!success) error = "Agent pipe write failed";
    return success;
}

inline bool ongoing(CommandChannel& pipe, bool stoppable, std::string& error) {
    if (!sent(pipe.sendConf_ongoingResult(), error)) return false;
    return !stoppable || sent(pipe.sendConf_stoppable(10000), error);
}

inline bool delay(CommandChannel& pipe, DWORD milliseconds, CommandInput& input,
    std::string& error) {
    const ULONGLONG deadline = GetTickCount64() + milliseconds;
    while (!input.stopped.load() && GetTickCount64() < deadline) {
        if (!pipe.connected()) {
            error = "Agent pipe disconnected";
            return false;
        }
        Sleep(25);
    }
    return true;
}

inline bool echo(CommandChannel& pipe, const Bytes& configuration, CommandInput&,
    std::string& error) {
    const std::string text(configuration.begin(), configuration.end());
    if (text.compare(0, 4, "ERR:") == 0) {
        error = "Simulated exception: " + text.substr(4);
        return false;
    }
    return sent(pipe.sendResult(configuration), error);
}

inline bool echoOngoing(CommandChannel& pipe, const Bytes& configuration,
    CommandInput& input, std::string& error) {
    if (!ongoing(pipe, false, error)) return false;
    const std::string text(configuration.begin(), configuration.end());
    for (int counter = 0; counter < 4 && !input.stopped.load(); ++counter) {
        if (!sent(pipe.sendResult(textBytes(std::to_string(counter) + ": " + text + "\n")), error))
            return false;
        if (!delay(pipe, 1000, input, error)) return false;
    }
    return sent(pipe.sendResult(textBytes("Stopping now\n")), error);
}

inline bool echoFile(CommandChannel& pipe, const Bytes& configuration,
    CommandInput& input, std::string& error) {
    if (configuration.size() < 4) {
        error = "File configuration is shorter than its line count";
        return false;
    }
    const std::uint32_t lines = std::uint32_t(configuration[0]) | (std::uint32_t(configuration[1]) << 8)
        | (std::uint32_t(configuration[2]) << 16) | (std::uint32_t(configuration[3]) << 24);
    const std::uint32_t maxLinesPerSecond = 2147483647u; // Java's signed int maximum.
    if (lines == 0 || lines > maxLinesPerSecond) {
        error = "Lines per second must be positive";
        return false;
    }
    if (!ongoing(pipe, true, error)) return false;
    const std::string text(configuration.begin() + 4, configuration.end());
    std::size_t begin = 0;
    std::uint32_t count = 0;
    while (begin <= text.size()) {
        const std::size_t end = text.find('\n', begin);
        const std::size_t length = end == std::string::npos ? text.size() - begin : end - begin;
        if (!sent(pipe.sendResult(textBytes(text.substr(begin, length) + "\n")), error)) return false;
        ++count;
        if (count % lines == 0 && !delay(pipe, 1000, input, error)) return false;
        if (input.stopped.load()) {
            if (!sent(pipe.sendResult(textBytes("=== USER FORCED STOP ===\n")), error)) return false;
            break;
        }
        if (end == std::string::npos) break;
        begin = end + 1;
    }
    return sent(pipe.sendResult(textBytes("Stopping now\n")), error);
}

inline bool echoMoreData(CommandChannel& pipe, const Bytes& configuration,
    CommandInput& input, std::string& error) {
    if (!ongoing(pipe, true, error)) return false;
    const std::string initial = "Initial data: " +
        std::string(configuration.begin(), configuration.end()) + "\n";
    if (!sent(pipe.sendResult(textBytes(initial)), error)) return false;
    for (;;) {
        Bytes update;
        const auto state = input.next(update);
        if (state == CommandInput::State::stopped) return true;
        if (!pipe.connected()) {
            error = "Agent pipe disconnected";
            return false;
        }
        if (state == CommandInput::State::idle) {
            Sleep(25);
            continue;
        }
        if (update.empty() || (update.size() == 1 && update[0] == 0)) return true;
        if (!sent(pipe.sendResult(textBytes("New data: " +
            std::string(update.begin(), update.end()) + "\n")), error)) return false;
    }
}
} // namespace echoexample
