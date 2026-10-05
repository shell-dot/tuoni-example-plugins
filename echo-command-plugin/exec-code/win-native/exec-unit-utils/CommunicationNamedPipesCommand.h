#pragma once

#include <cstdint>
#include <vector>
#include <functional>

#include "CommunicationNamedPipes.h"

namespace ExecUnitUtils
{
    class CommunicationNamedPipesCommand : public CommunicationNamedPipes
    {
    public:
        using NewDataCallback = std::function<void(const std::vector<std::uint8_t>&)>;
        using StopCallback = std::function<void()>;

#ifdef _WIN32
        CommunicationNamedPipesCommand(const char* pipeName,
            NewDataCallback newData,
            StopCallback stop,
            const CommunicationNamedPipesOptions& options = CommunicationNamedPipesOptions());
#else
        CommunicationNamedPipesCommand(const char* pipeNameRead,
            const char* pipeNameWrite,
            NewDataCallback newData,
            StopCallback stop);
#endif
        ~CommunicationNamedPipesCommand() noexcept;

        bool TrySendResult(
            const std::vector<std::uint8_t>& data,
            NamedPipeTransportError* error = nullptr);
        bool TrySendError(
            const std::vector<std::uint8_t>& msg,
            NamedPipeTransportError* error = nullptr);
        bool TrySendReturnSuccess(NamedPipeTransportError* error = nullptr);
        bool TrySendReturnFailed(NamedPipeTransportError* error = nullptr);
        bool TrySendConfOngoingResult(NamedPipeTransportError* error = nullptr);
        bool TrySendConfStoppable(
            std::uint32_t waitTime,
            NamedPipeTransportError* error = nullptr);

        bool sendResult(const std::vector<std::uint8_t>& data);
        bool sendError(const std::vector<std::uint8_t>& msg);
        bool sendReturnSuccess();
        bool sendReturnFailed();
        bool sendConf_ongoingResult();
        bool sendConf_stoppable(std::uint32_t waitTime);

    protected:
        bool handleIncomingData(TLVPtr& tlv) override;

        static constexpr std::uint8_t MessageTypeResult = 0x30;
        static constexpr std::uint8_t MessageTypeConf = 0x31;
        static constexpr std::uint8_t MessageTypeConf_ongoing = 0x01;
        static constexpr std::uint8_t MessageTypeConf_stoppable = 0x03;
        static constexpr std::uint8_t MessageTypeError = 0x32;
        static constexpr std::uint8_t MessageTypeSuccess = 0x33;
        static constexpr std::uint8_t MessageTypeFailed = 0x34;
        static constexpr std::uint8_t MessageTypeStop = 0x3F;
        static constexpr std::uint8_t MessageTypeNewData = 0x39;

        NewDataCallback _actionNewData;
        StopCallback    _actionStop;
    };

} // namespace ExecUnitUtils
