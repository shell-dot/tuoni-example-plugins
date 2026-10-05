#pragma once
#include "CommandRuntime.h"

#include <limits>

namespace echoexample {
using namespace commandexample;

inline void ongoing(CommandChannel& pipe, bool stoppable) {
    requireSend(pipe.sendConf_ongoingResult());
    if (stoppable) requireSend(pipe.sendConf_stoppable(10000));
}

inline void delay(CommandChannel& pipe, DWORD milliseconds, CommandInput& input) {
    const ULONGLONG deadline = GetTickCount64() + milliseconds;
    while (!input.stopped.load() && GetTickCount64() < deadline) {
        if (!pipe.connected()) throw std::runtime_error("Agent pipe disconnected");
        Sleep(25);
    }
}

inline void echo(CommandChannel& pipe, const Bytes& configuration, CommandInput&) {
    const std::string text(configuration.begin(), configuration.end());
    if (text.compare(0, 4, "ERR:") == 0)
        throw std::runtime_error("Simulated exception: " + text.substr(4));
    requireSend(pipe.sendResult(configuration));
}

inline void echoOngoing(CommandChannel& pipe, const Bytes& configuration, CommandInput& input) {
    ongoing(pipe, false);
    const std::string text(configuration.begin(), configuration.end());
    for (int counter = 0; counter < 4 && !input.stopped.load(); ++counter) {
        requireSend(pipe.sendResult(textBytes(std::to_string(counter) + ": " + text + "\n")));
        delay(pipe, 1000, input);
    }
    requireSend(pipe.sendResult(textBytes("Stopping now\n")));
}

inline void echoFile(CommandChannel& pipe, const Bytes& configuration, CommandInput& input) {
    if (configuration.size() < 4)
        throw std::invalid_argument("File configuration is shorter than its line count");
    const std::uint32_t lines = std::uint32_t(configuration[0]) | (std::uint32_t(configuration[1]) << 8)
        | (std::uint32_t(configuration[2]) << 16) | (std::uint32_t(configuration[3]) << 24);
    if (lines == 0 || lines > static_cast<std::uint32_t>((std::numeric_limits<std::int32_t>::max)()))
        throw std::invalid_argument("Lines per second must be positive");
    ongoing(pipe, true);
    const std::string text(configuration.begin() + 4, configuration.end());
    std::size_t begin = 0;
    std::uint32_t count = 0;
    while (begin <= text.size()) {
        const std::size_t end = text.find('\n', begin);
        requireSend(pipe.sendResult(textBytes(text.substr(begin, end == std::string::npos
            ? text.size() - begin : end - begin) + "\n")));
        if (++count % lines == 0) delay(pipe, 1000, input);
        if (input.stopped.load()) {
            requireSend(pipe.sendResult(textBytes("=== USER FORCED STOP ===\n")));
            break;
        }
        if (end == std::string::npos) break;
        begin = end + 1;
    }
    requireSend(pipe.sendResult(textBytes("Stopping now\n")));
}

inline void echoMoreData(CommandChannel& pipe, const Bytes& configuration, CommandInput& input) {
    ongoing(pipe, true);
    requireSend(pipe.sendResult(textBytes("Initial data: " +
        std::string(configuration.begin(), configuration.end()) + "\n")));
    for (;;) {
        Bytes update;
        const auto state = input.next(update);
        if (state == CommandInput::State::stopped) return;
        if (!pipe.connected()) throw std::runtime_error("Agent pipe disconnected");
        if (state == CommandInput::State::idle) { Sleep(25); continue; }
        if (update.empty() || (update.size() == 1 && update[0] == 0)) return;
        requireSend(pipe.sendResult(textBytes("New data: " +
            std::string(update.begin(), update.end()) + "\n")));
    }
}
} // namespace echoexample
