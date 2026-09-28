#include "CommunicationNamedPipes.h"

#include <fcntl.h>
#include <unistd.h>

std::vector<uint8_t> CommunicationNamedPipes::connect()
{
    pipe_read = open(pipeNameRead.c_str(), O_RDONLY);
    if (pipe_read == -1)
    {
        return {};
    }

    pipe_write = open(pipeNameWrite.c_str(), O_WRONLY);
    if (pipe_write == -1)
    {
        close();
        return {};
    }

    ssize_t bytes_written = write(pipe_write, "\x00", 1);
    (void)bytes_written;

    active = true;
    auto data = getData();
    TLV tlv;
    if (!tlv.load(data))
    {
        active = false;
        return {};
    }

    startListenerIfNeeded();
    return tlv.getValue();
}

std::vector<uint8_t> CommunicationNamedPipes::getData()
{
    if (!active)
    {
        return {};
    }

    uint32_t len;
    ssize_t bytes_read = read(pipe_read, &len, sizeof(len));
    if (bytes_read <= 0)
    {
        return {};
    }

    std::vector<uint8_t> buffer(len);
    uint32_t offset = 0;
    while (len > 0)
    {
        bytes_read = read(pipe_read, buffer.data() + offset, len);
        if (bytes_read <= 0)
        {
            return {};
        }
        offset += bytes_read;
        len -= bytes_read;
    }
    return buffer;
}

bool CommunicationNamedPipes::putData(const std::vector<uint8_t> &data)
{
    std::lock_guard<std::mutex> lock(mtx);
    if (!active)
    {
        return false;
    }

    uint32_t len = data.size();
    if (write(pipe_write, &len, sizeof(len)) == -1 || write(pipe_write, data.data(), len) == -1)
    {
        return false;
    }

    return true;
}

void CommunicationNamedPipes::close()
{
    if (pipe_read != -1)
    {
        ::close(pipe_read);
        pipe_read = -1;
    }
    if (pipe_write != -1)
    {
        ::close(pipe_write);
        pipe_write = -1;
    }
    active = false;
}

void CommunicationNamedPipes::sendResult(const std::vector<uint8_t> &data)
{
    if (!active)
    {
        return;
    }
    TLV tlv(0x30, data);
    putData(tlv.genBytes());
}

void CommunicationNamedPipes::sendError(const std::vector<uint8_t> &data)
{
    if (!active)
    {
        return;
    }
    TLV tlv(0x32, data);
    putData(tlv.genBytes());
}

void CommunicationNamedPipes::sendReturnSuccess()
{
    if (!active)
    {
        return;
    }
    TLV tlv(0x33);
    putData(tlv.genBytes());
}

void CommunicationNamedPipes::sendReturnFailed()
{
    if (!active)
    {
        return;
    }
    TLV tlv(0x34);
    putData(tlv.genBytes());
}

void CommunicationNamedPipes::sendConf_ongoingResult()
{
    if (!active)
    {
        return;
    }
    TLV tlv(0x31);
    tlv.addChild(std::shared_ptr<TLV>(new TLV(0x1, (PVOID)"\x01", 1)));
    putData(tlv.genBytes());
}

void CommunicationNamedPipes::sendConf_relayInBlocks()
{
    if (!active)
    {
        return;
    }
    TLV tlv(0x31);
    tlv.addChild(std::shared_ptr<TLV>(new TLV(0x2, (PVOID)"\x01", 1)));
    putData(tlv.genBytes());
}

void CommunicationNamedPipes::sendConf_stoppable(uint32_t waitTime)
{
    if (!active)
    {
        return;
    }
    TLV tlv(0x31);
    tlv.addChild(std::shared_ptr<TLV>(new TLV(0x3, (PVOID)&waitTime, sizeof(waitTime))));
    putData(tlv.genBytes());
}

void CommunicationNamedPipes::setCallback(CallbackFunc* callbackIn)
{
    setCallbackNewData(callbackIn);
}

void CommunicationNamedPipes::setCallbackNewData(CallbackFunc* callbackIn)
{
    callbackNewData = callbackIn;
    startListenerIfNeeded();
}

void CommunicationNamedPipes::setCallbackStop(CallbackFuncStop* callbackIn)
{
    callbackStop = callbackIn;
    startListenerIfNeeded();
}

void CommunicationNamedPipes::startListenerIfNeeded()
{
    if (!active || listenerStarted || (!callbackNewData && !callbackStop))
    {
        return;
    }

    listenerStarted = true;
    listen_thread = std::thread(&CommunicationNamedPipes::listenForMessages, this);
    listen_thread.detach();
}

void CommunicationNamedPipes::listenForMessages()
{
    while (true)
    {
        auto data = getData();
        if (data.empty())
        {
            return;
        }

        std::shared_ptr<TLV> tlv(new TLV());
        if (!tlv->load(data))
        {
            continue;
        }

        if (tlv->getType() == 0x39 && callbackNewData)
        {
            callbackNewData(tlv->getValue());
            continue;
        }
        if (tlv->getType() == 0x3F && callbackStop)
        {
            callbackStop();
            continue;
        }
    }
}
