#include "TLV.h"

#ifdef _WIN32
#define NOMINMAX
#include <Windows.h>
#endif // _WIN32

namespace ExecUnitUtils
{
#ifdef _WIN32
    std::wstring utf8ToWString(const std::string& utf8)
    {
        if (utf8.empty())
            return std::wstring();

        int required = ::MultiByteToWideChar(
            CP_UTF8,
            MB_ERR_INVALID_CHARS,
            utf8.data(),
            static_cast<int>(utf8.size()),
            nullptr,
            0);

        if (required <= 0)
            return std::wstring();

        std::wstring result(static_cast<size_t>(required), L'\0');
        int converted = ::MultiByteToWideChar(
            CP_UTF8,
            MB_ERR_INVALID_CHARS,
            utf8.data(),
            static_cast<int>(utf8.size()),
            &result[0],
            required);

        if (converted != required)
            return std::wstring();

        return result;
    }

    std::string wStringToUtf8(const std::wstring& wstr)
    {
        if (wstr.empty())
            return std::string();

        int required = ::WideCharToMultiByte(
            CP_UTF8,
            WC_ERR_INVALID_CHARS,
            wstr.data(),
            static_cast<int>(wstr.size()),
            nullptr,
            0,
            nullptr,
            nullptr);

        if (required <= 0)
            return std::string();

        std::string result(static_cast<size_t>(required), '\0');
        int converted = ::WideCharToMultiByte(
            CP_UTF8,
            WC_ERR_INVALID_CHARS,
            wstr.data(),
            static_cast<int>(wstr.size()),
            &result[0],
            required,
            nullptr,
            nullptr);

        if (converted != required)
            return std::string();

        return result;
    }
#endif // _WIN32

    TLV::TLV()
    {
    }

    TLV::TLV(uint8_t typeIn, const std::vector<uint8_t>& dataIn)
    {
        m_type = typeIn;
        m_isParent = false;
        m_data = dataIn;
        m_fullSize = static_cast<uint32_t>(m_data.size() + 5u);
    }

    TLV::TLV(uint8_t typeIn, std::vector<uint8_t>&& dataIn)
    {
        m_type = typeIn;
        m_isParent = false;
        m_data = std::move(dataIn);
        m_fullSize = static_cast<uint32_t>(m_data.size() + 5u);
    }

    TLV::TLV(uint8_t typeIn)
    {
        m_type = typeIn;
        m_isParent = true;
        m_fullSize = 5u;
    }

    void TLV::makeLeaf(uint8_t typeIn, const uint8_t* data, size_t length)
    {
        m_type = typeIn;
        m_isParent = false;
        m_children.clear();
        m_data.assign(data, data + length);
        m_fullSize = static_cast<uint32_t>(length + 5u);
    }

    bool TLV::load(const uint8_t* buffer, size_t bufferSize, size_t offset)
    {
        if (!buffer)
            return false;

        if (offset > bufferSize || bufferSize - offset < 5u)
            return false;

        uint8_t typeByte = buffer[offset];
        m_type = static_cast<uint8_t>(typeByte & 0x7Fu);
        m_isParent = (typeByte & 0x80u) != 0;
        offset += 1u;

        if (offset > bufferSize || bufferSize - offset < 4u)
            return false;

        uint32_t len = 0;
        std::memcpy(&len, buffer + offset, sizeof(uint32_t));
        offset += 4u;

        if (offset > bufferSize || static_cast<size_t>(len) > bufferSize - offset)
            return false;

        m_fullSize = len + 5u;
        m_data.clear();
        m_children.clear();

        if (!m_isParent)
        {
            m_data.assign(buffer + offset, buffer + offset + len);
            return true;
        }

        size_t remaining = len;
        while (remaining != 0u)
        {
            auto child = std::make_shared<TLV>();
            if (!child->load(buffer, bufferSize, offset))
                return false;

            if (child->m_fullSize > remaining || child->m_fullSize == 0)
                return false;

            addChildInternal(child);

            offset += child->m_fullSize;
            remaining -= child->m_fullSize;
        }

        return true;
    }

    bool TLV::loadExact(
        const uint8_t* buffer,
        size_t bufferSize,
        size_t maxNodes,
        size_t maxDepth)
    {
        if (!buffer || maxNodes == 0u || maxDepth == 0u)
            return false;

        struct Header final
        {
            uint8_t type = 0;
            bool parent = false;
            size_t payloadStart = 0;
            size_t end = 0;
            uint32_t length = 0;
        };

        auto readHeader = [buffer, bufferSize](
            size_t offset, size_t containingEnd, Header& header) -> bool
        {
            if (containingEnd > bufferSize || offset > containingEnd
                || containingEnd - offset < 5u)
            {
                return false;
            }

            const uint8_t wireType = buffer[offset];
            uint32_t wireLength = 0;
            std::memcpy(&wireLength, buffer + offset + 1u, sizeof(wireLength));
            const size_t payloadStart = offset + 5u;
            if (static_cast<size_t>(wireLength) > containingEnd - payloadStart)
                return false;

            header.type = static_cast<uint8_t>(wireType & 0x7Fu);
            header.parent = (wireType & 0x80u) != 0u;
            header.payloadStart = payloadStart;
            header.end = payloadStart + static_cast<size_t>(wireLength);
            header.length = wireLength;
            return true;
        };

        auto initialize = [buffer](TLV& value, const Header& header)
        {
            value.m_type = header.type;
            value.m_isParent = header.parent;
            value.m_fullSize = header.length + 5u;
            value.m_children.clear();
            value.m_data.clear();
            if (!header.parent)
            {
                value.m_data.assign(
                    buffer + header.payloadStart,
                    buffer + header.end);
            }
        };

        Header rootHeader;
        if (!readHeader(0u, bufferSize, rootHeader)
            || rootHeader.end != bufferSize)
        {
            return false;
        }

        initialize(*this, rootHeader);
        if (!rootHeader.parent)
            return true;

        struct Frame final
        {
            TLV* node;
            size_t cursor;
            size_t end;
            size_t depth;
        };

        size_t nodeCount = 1u;
        std::vector<Frame> stack;
        stack.push_back(Frame{
            this, rootHeader.payloadStart, rootHeader.end, 1u });

        while (!stack.empty())
        {
            Frame& frame = stack.back();
            if (frame.cursor == frame.end)
            {
                stack.pop_back();
                continue;
            }

            Header childHeader;
            if (!readHeader(frame.cursor, frame.end, childHeader))
                return false;
            if (++nodeCount > maxNodes)
                return false;
            const size_t childDepth = frame.depth + 1u;
            if (childDepth > maxDepth)
                return false;

            auto child = std::make_shared<TLV>();
            initialize(*child, childHeader);
            frame.node->addChildInternal(child);
            frame.cursor = childHeader.end;

            if (childHeader.parent)
            {
                stack.push_back(Frame{
                    child.get(), childHeader.payloadStart, childHeader.end, childDepth });
            }
        }
        return true;
    }

    bool TLV::addChild(const TLV& child)
    {
        if (!m_isParent)
            return false;

        auto ptr = std::make_shared<TLV>(child);
        addChildInternal(ptr);

        m_fullSize = static_cast<uint32_t>(m_fullSize + child.m_fullSize);
        return true;
    }

    void TLV::addChildInternal(const TLVPtr& child)
    {
        auto it = m_children.find(child->m_type);
        if (it == m_children.end())
        {
            m_children[child->m_type] = std::vector<TLVPtr>{ child };
        }
        else
        {
            it->second.push_back(child);
        }
    }

    TLVPtr TLV::getChild(uint8_t childType, size_t idx)
    {
        auto it = m_children.find(childType);
        if (it == m_children.end())
            return nullptr;
        if (idx >= it->second.size())
            return nullptr;
        return it->second[idx];
    }

    const TLVPtr TLV::getChild(uint8_t childType, size_t idx) const
    {
        auto it = m_children.find(childType);
        if (it == m_children.end())
            return nullptr;
        if (idx >= it->second.size())
            return nullptr;
        return it->second[idx];
    }

    size_t TLV::getChildCount(uint8_t childType) const
    {
        auto it = m_children.find(childType);
        if (it == m_children.end())
            return 0u;
        return it->second.size();
    }

    void TLV::writeFullBuffer(std::vector<uint8_t>& out) const
    {
        uint8_t typeByte = static_cast<uint8_t>(m_type | (m_isParent ? 0x80u : 0x00u));
        out.push_back(typeByte);

        uint32_t valueLen = m_fullSize >= 5u ? (m_fullSize - 5u) : 0u;
        uint8_t lenBytes[4];
        std::memcpy(lenBytes, &valueLen, sizeof(uint32_t));
        out.insert(out.end(), lenBytes, lenBytes + 4);

        if (!m_isParent)
        {
            out.insert(out.end(), m_data.begin(), m_data.end());
        }
        else
        {
            for (const auto& kv : m_children)
            {
                for (const auto& child : kv.second)
                {
                    child->writeFullBuffer(out);
                }
            }
        }
    }

    std::vector<uint8_t> TLV::getFullBuffer() const
    {
        std::vector<uint8_t> buffer;
        buffer.reserve(m_fullSize ? m_fullSize : 5u);
        writeFullBuffer(buffer);
        return buffer;
    }

    bool TLV::getAsString(std::string& out) const
    {
        if (m_isParent || m_data.empty())
            return false;

        std::string tmp(reinterpret_cast<const char*>(m_data.data()), m_data.size());
        out = std::move(tmp);
        return true;
    }

#ifdef _WIN32
    bool TLV::getAsWString(std::wstring& out) const
    {
        if (m_isParent || m_data.empty())
            return false;

        std::string utf8(reinterpret_cast<const char*>(m_data.data()), m_data.size());
        std::wstring w = utf8ToWString(utf8);

        if (w.empty())
            return false;

        out = std::move(w);
        return true;
    }
#endif // _WIN32

    void TLV::setFromString(uint8_t typeIn, const std::string& utf8)
    {
        m_type = typeIn;
        m_isParent = false;
        m_children.clear();

        m_data.assign(utf8.begin(), utf8.end());
        m_fullSize = static_cast<uint32_t>(m_data.size() + 5u);
    }

#ifdef _WIN32
    void TLV::setFromWString(uint8_t typeIn, const std::wstring& wstr)
    {
        std::string utf8 = wStringToUtf8(wstr);
        setFromString(typeIn, utf8);
    }
#endif // _WIN32

    bool TLV::getAsByte(uint8_t& out) const
    {
        if (m_isParent || m_data.size() != 1u)
            return false;
        out = m_data[0];
        return true;
    }

    bool TLV::getAsSByte(int8_t& out) const
    {
        if (m_isParent || m_data.size() != 1u)
            return false;
        out = static_cast<int8_t>(m_data[0]);
        return true;
    }

    bool TLV::getAsBool(bool& out) const
    {
        if (m_isParent || m_data.size() != 1u)
            return false;
        out = (m_data[0] != 0u);
        return true;
    }

    bool TLV::getAsInt16(int16_t& out) const { return getIntegral<int16_t>(out); }
    bool TLV::getAsUInt16(uint16_t& out) const { return getIntegral<uint16_t>(out); }
    bool TLV::getAsInt32(int32_t& out) const { return getIntegral<int32_t>(out); }
    bool TLV::getAsUInt32(uint32_t& out) const { return getIntegral<uint32_t>(out); }
    bool TLV::getAsInt64(int64_t& out) const { return getIntegral<int64_t>(out); }
    bool TLV::getAsUInt64(uint64_t& out) const { return getIntegral<uint64_t>(out); }
    bool TLV::getAsSingle(float& out) const { return getIntegral<float>(out); }
    bool TLV::getAsDouble(double& out) const { return getIntegral<double>(out); }

    bool TLV::getAsBytes(std::vector<uint8_t>& out) const
    {
        if (m_isParent)
            return false;

        out = m_data;
        return true;
    }

    std::string TLV::toString() const
    {
        std::ostringstream oss;
        oss << "TLV(Type=" << static_cast<int>(m_type)
            << ", IsParent=" << (m_isParent ? "true" : "false")
            << ", FullSize=" << m_fullSize
            << ", ChildrenTypes=" << m_children.size() << ")";
        return oss.str();
    }

} // namespace ExecUnitUtils
