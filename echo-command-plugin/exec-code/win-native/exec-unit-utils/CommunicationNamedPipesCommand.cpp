#include "CommunicationNamedPipesCommand.h"
#include "TLV.h"
#include <utility> 

namespace ExecUnitUtils
{

#ifdef _WIN32
    CommunicationNamedPipesCommand::CommunicationNamedPipesCommand(
        const char* pipeName,
        NewDataCallback newData,
        StopCallback stop,
        const CommunicationNamedPipesOptions& options)
        : CommunicationNamedPipes(pipeName, options),
        _actionNewData(std::move(newData)),
        _actionStop(std::move(stop))
    {
    }
#else
    CommunicationNamedPipesCommand::CommunicationNamedPipesCommand(
        const char* pipeNameRead,
        const char* pipeNameWrite,
        NewDataCallback newData,
        StopCallback stop)
        : CommunicationNamedPipes(pipeNameRead, pipeNameWrite),
        _actionNewData(std::move(newData)),
        _actionStop(std::move(stop))
    {
    }
#endif

    CommunicationNamedPipesCommand::~CommunicationNamedPipesCommand() noexcept
    {
        // Stop and join the base listener while the callbacks it dispatches to are
        // still alive. Waiting until the base destructor would destroy these
        // std::function members first and permit a disconnect race with dispatch.
        (void)dispose();
    }

    bool CommunicationNamedPipesCommand::TrySendResult(
        const std::vector<std::uint8_t>& data,
        NamedPipeTransportError* error)
    {
        TLV tlv(MessageTypeResult, data);
        std::vector<std::uint8_t> buffer = tlv.getFullBuffer();
        return TrySend(buffer, error);
    }

    bool CommunicationNamedPipesCommand::sendResult(const std::vector<std::uint8_t>& data)
    {
        return TrySendResult(data);
    }

    bool CommunicationNamedPipesCommand::TrySendError(
        const std::vector<std::uint8_t>& msg,
        NamedPipeTransportError* error)
    {
        TLV tlv(MessageTypeError, msg);
        std::vector<std::uint8_t> buffer = tlv.getFullBuffer();
        return TrySend(buffer, error);
    }

    bool CommunicationNamedPipesCommand::sendError(const std::vector<std::uint8_t>& msg)
    {
        return TrySendError(msg);
    }

    bool CommunicationNamedPipesCommand::TrySendReturnSuccess(
        NamedPipeTransportError* error)
    {
        std::vector<std::uint8_t> empty;
        TLV tlv(MessageTypeSuccess, empty);
        std::vector<std::uint8_t> buffer = tlv.getFullBuffer();
        return TrySend(buffer, error);
    }

    bool CommunicationNamedPipesCommand::sendReturnSuccess()
    {
        return TrySendReturnSuccess();
    }

    bool CommunicationNamedPipesCommand::TrySendReturnFailed(
        NamedPipeTransportError* error)
    {
        std::vector<std::uint8_t> empty;
        TLV tlv(MessageTypeFailed, empty);
        std::vector<std::uint8_t> buffer = tlv.getFullBuffer();
        return TrySend(buffer, error);
    }

    bool CommunicationNamedPipesCommand::sendReturnFailed()
    {
        return TrySendReturnFailed();
    }

    bool CommunicationNamedPipesCommand::TrySendConfOngoingResult(
        NamedPipeTransportError* error)
    {
        TLV tlv(MessageTypeConf);
        std::vector<std::uint8_t> value(1, 0x01);
        TLV child(MessageTypeConf_ongoing, value);
        tlv.addChild(child);

        std::vector<std::uint8_t> buffer = tlv.getFullBuffer();
        return TrySend(buffer, error);
    }

    bool CommunicationNamedPipesCommand::sendConf_ongoingResult()
    {
        return TrySendConfOngoingResult();
    }

    bool CommunicationNamedPipesCommand::TrySendConfStoppable(
        std::uint32_t waitTime,
        NamedPipeTransportError* error)
    {
        TLV tlv(MessageTypeConf);
        std::vector<std::uint8_t> value(sizeof(waitTime));
        value[0] = static_cast<std::uint8_t>(waitTime & 0xFF);
        value[1] = static_cast<std::uint8_t>((waitTime >> 8) & 0xFF);
        value[2] = static_cast<std::uint8_t>((waitTime >> 16) & 0xFF);
        value[3] = static_cast<std::uint8_t>((waitTime >> 24) & 0xFF);
        TLV child(MessageTypeConf_stoppable, value);
        tlv.addChild(child);

        std::vector<std::uint8_t> buffer = tlv.getFullBuffer();
        return TrySend(buffer, error);
    }

    bool CommunicationNamedPipesCommand::sendConf_stoppable(std::uint32_t waitTime)
    {
        return TrySendConfStoppable(waitTime);
    }

    bool CommunicationNamedPipesCommand::handleIncomingData(TLVPtr& tlv)
    {
        if (!tlv) {
            return false;
        }

        std::uint8_t type = tlv->getType();

        if (type == MessageTypeStop && !tlv->isParent()) {
            std::vector<std::uint8_t> data;
            if (!tlv->getAsBytes(data) || !data.empty())
                return false;
            if (_actionStop) {
                _actionStop();
            }
            return true;
        }

        if (type == MessageTypeNewData && !tlv->isParent()) {
            if (_actionNewData) {
                std::vector<std::uint8_t> data;
                if (tlv->getAsBytes(data)) {
                    _actionNewData(data);
                }
            }
            return true;
        }

        return false;
    }

} // namespace ExecUnitUtils
