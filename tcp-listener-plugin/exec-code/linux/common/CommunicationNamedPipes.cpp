#include "CommunicationNamedPipes.h"

void CommunicationNamedPipes::setCallback(CallbackFunc* callbackIn)
{
    callback = callbackIn;
}

std::vector<uint8_t> CommunicationNamedPipes::connect()
{
    pipe_read = open(pipeNameRead.c_str(), O_RDONLY);
    if (pipe_read == -1)
    {
        std::cerr << "Failed to connect to the pipe" << std::endl;
        return {};
    }

    pipe_write = open(pipeNameWrite.c_str(), O_WRONLY);
    if (pipe_write == -1)
    {
        close();
        return {};
    }

    write(pipe_write, "\x00", 1);

    active = true;
    auto data = getData();
    TLV tlv;
    if (!tlv.load(data))
    {
        active = false;
        return {};
    }

    listen_thread = std::thread(&CommunicationNamedPipes::listenForMessages, this);
    return tlv.getValue();
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

        if (tlv->getType() == 0x20 && callback)
        {
            callback(tlv->getChild(0x4)->getValue());
            continue;
        }
        if ((tlv->getType() == 0x21 || tlv->getType() == 0x22) && tlv->getChild(0x2) != nullptr)
        {
            std::unique_lock<std::mutex> lock(mtx);
            int id = tlv->getChild(0x2)->getUInt32();
            responses[id] = tlv;
            if(signal.count(id))
            {
                sem_post(&signal[id]);
            }
        }
    }
}

std::vector<uint8_t> CommunicationNamedPipes::getData()
{
    if (!active)
        return {};

    uint32_t len;
    ssize_t bytes_read = read(pipe_read, &len, sizeof(len));
    if (bytes_read <= 0)
    {
        return {};
    }

    std::vector<uint8_t> buffer(len);
    uint32_t offset = 0;
    while(len > 0)
    {
        bytes_read = read(pipe_read, buffer.data() + offset, len);
        offset += bytes_read;
        len -= bytes_read;
        if (bytes_read <= 0)
        {
            return {};
        }
    }
    return buffer;
}

bool CommunicationNamedPipes::putData(const std::vector<uint8_t> &data)
{
    std::lock_guard<std::mutex> lock(mtx);
    if (!active)
        return false;

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
    }
    if (pipe_write != -1)
    {
        ::close(pipe_write);
    }
    active = false;
    if (listen_thread.joinable())
    {
        listen_thread.join();
    }
}


void CommunicationNamedPipes::newDataFromC2(std::vector<uint8_t> data)
{
    if (!active)
        return;

    TLV tlv(0x23, data);
    putData(tlv.genBytes());
}

std::vector<uint8_t> CommunicationNamedPipes::getMetadata()
{
    if (!active)
        return {};

    TLV tlv(0x21);
    tlv.addChild(std::shared_ptr<TLV>(new TLV(0x1, std::vector<uint8_t>{0x1})));
    int seqNrKeep = seqNr++;
    tlv.addChild(std::shared_ptr<TLV>(new TLV(0x2, &seqNrKeep, sizeof(seqNrKeep))));
    putData(tlv.genBytes());
    return waitForResponseData(seqNrKeep);
}

std::vector<uint8_t> CommunicationNamedPipes::getDataToSend()
{
    if (!active)
        return {};

    TLV tlv(0x22);
    tlv.addChild(std::shared_ptr<TLV>(new TLV(0x1, std::vector<uint8_t>{0x1})));
    int seqNrKeep = seqNr++;
    tlv.addChild(std::shared_ptr<TLV>(new TLV(0x2, &seqNrKeep, sizeof(seqNrKeep))));
    putData(tlv.genBytes());
    return waitForResponseData(seqNrKeep);
}

std::vector<uint8_t> CommunicationNamedPipes::waitForResponseData(int id)
{
    std::shared_ptr<TLV> tlv = NULL;
    
    {
        std::unique_lock<std::mutex> lock(mtx);
        if(responses.count(id))
        {
            tlv = responses[id];
            responses.erase(id);
        }
        else
        {
            signal[id] = sem_t();
            sem_init(&signal[id], 0, 0);
        }
    }

    if(!tlv.get())
    {
        sem_wait(&signal[id]);
        {
            std::unique_lock<std::mutex> lock(mtx);
            tlv = responses[id];
            sem_destroy(&signal[id]);
            responses.erase(id);
            signal.erase(id);
        }
    }

    if (tlv->getChild(0x4) == nullptr)
    {
        return {};
    }
    return tlv->getChild(0x4)->getValue();
}