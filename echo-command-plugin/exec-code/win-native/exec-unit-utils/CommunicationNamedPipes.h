#pragma once

#include <string>
#include <vector>
#include <atomic>
#include <mutex>
#include <condition_variable>
#include <unordered_map>
#include <utility>
#include <memory>
#include <array>
#include <cstdint>
#include <limits>
#include "TLV.h"

#ifdef _WIN32
#include <windows.h>
#endif

namespace ExecUnitUtils {
    enum class NamedPipeFailureCategory : std::uint8_t
    {
        None = 0,
        Validation,
        Windows,
        Canceled,
        Unsupported,
        Timeout,
        Transport,
        Limit,
        Unstable,
        Internal
    };

    struct NamedPipeTransportError final
    {
        NamedPipeFailureCategory category = NamedPipeFailureCategory::None;
        std::uint32_t windowsError = 0;
        std::array<char, 160> text{};

        void clear() noexcept
        {
            category = NamedPipeFailureCategory::None;
            windowsError = 0;
            text.fill('\0');
        }

        bool failed() const noexcept
        {
            return category != NamedPipeFailureCategory::None;
        }
    };

    struct CommunicationNamedPipesOptions
    {
        std::uint32_t maxInboundFrameBytes = (std::numeric_limits<std::uint32_t>::max)();
        int initialReadTimeoutMs = -1;
        int partialReadTimeoutMs = -1;
        int writeTimeoutMs = -1;
        int closeTimeoutMs = 2000;
        bool rejectEmptyFrames = false;
        bool exactEnvelopes = false;
        bool allowRequestResponses = true;
        bool connectDeadlineIncludesInitialFrame = false;
        std::size_t maxPendingResponses = 64u;

        bool valid() const noexcept
        {
            return maxInboundFrameBytes != 0u
                && initialReadTimeoutMs >= -1
                && partialReadTimeoutMs >= -1
                && writeTimeoutMs >= -1
                && closeTimeoutMs >= 0
                && maxPendingResponses != 0u
                && maxPendingResponses <= 64u;
        }

        static CommunicationNamedPipesOptions structuredCommand()
        {
            CommunicationNamedPipesOptions result;
            result.maxInboundFrameBytes = 1024U * 1024U;
            result.initialReadTimeoutMs = 10000;
            result.partialReadTimeoutMs = 10000;
            result.writeTimeoutMs = 10000;
            result.closeTimeoutMs = 2000;
            result.rejectEmptyFrames = true;
            result.exactEnvelopes = true;
            result.allowRequestResponses = false;
            result.connectDeadlineIncludesInitialFrame = true;
            return result;
        }

    };

    class CommunicationNamedPipes
    {
    public:
#ifdef _WIN32
        CommunicationNamedPipes(
            const char* pipeName,
            const CommunicationNamedPipesOptions& options = CommunicationNamedPipesOptions());
#else
        CommunicationNamedPipes(const char* pipeNameRead, const char* pipeNameWrite);
#endif
        ~CommunicationNamedPipes() noexcept;
        std::vector<std::uint8_t> connect(int timeoutMs = 10000);
        bool TryConnect(
            std::vector<std::uint8_t>& configuration,
            NamedPipeTransportError* error = nullptr,
            int timeoutMs = 10000);
        bool TrySend(
            const std::vector<std::uint8_t>& frame,
            NamedPipeTransportError* error = nullptr);
        bool TryClose(NamedPipeTransportError* error = nullptr) noexcept;
        void close() noexcept;

        // Blocking 0x3A request/response. Returns <username,password>; both empty on failure/timeout.
        std::pair<std::string, std::string> getCurrentCredentials(int timeoutMs = 10000);

    protected:
        static constexpr int defaultConnectTimeoutMs = 5000;
        virtual bool handleIncomingData(TLVPtr& tlv);

        void listenForMessages();
        bool getData(
            std::vector<std::uint8_t>& outData,
            bool initialFrame = false,
            int initialTimeoutOverrideMs = (std::numeric_limits<int>::min)(),
            NamedPipeTransportError* error = nullptr);
        bool putData(const std::vector<std::uint8_t>& data);
        bool dispose(NamedPipeTransportError* error = nullptr) noexcept;

        // Waits up to timeoutMs for a 0x3A response matching seq. Returns nullptr on timeout.
        TLVPtr waitForResponseTLV(int32_t seq, int timeoutMs);

    protected:
        std::atomic<bool>   _active;
        std::atomic<bool>   _cancelRequested;
        CommunicationNamedPipesOptions _options;
        bool                _optionsValid;

        std::atomic<int32_t>                                           _seqNr;
        std::mutex                                                     _responsesLock;
        std::unordered_map<int32_t, TLVPtr>                            _responses;
        std::unordered_map<int32_t, std::shared_ptr<std::condition_variable>> _signals;


#ifdef _WIN32
        std::atomic<HANDLE> _handle;
        HANDLE              _shutdownEvent;
        std::atomic<HANDLE> _listenThreadHandle;
        std::atomic<DWORD>  _listenerThreadId;
        SRWLOCK             _sendLock;
        SRWLOCK             _disposeLock;
        SRWLOCK             _joinLock;
        std::string         _pipeName;
#else
        int                 _fdRead;
        int                 _fdWrite;
        std::string         _pipeNameRead;
        std::string         _pipeNameWrite;
#endif

    private:
#ifdef _WIN32
        static unsigned __stdcall listenThreadEntry(void* context) noexcept;
#endif
        CommunicationNamedPipes(const CommunicationNamedPipes&) = delete;
        CommunicationNamedPipes& operator=(const CommunicationNamedPipes&) = delete;
    };

}
