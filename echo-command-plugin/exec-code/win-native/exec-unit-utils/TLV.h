#pragma once

#include <cstdint>
#include <vector>
#include <unordered_map>
#include <memory>
#include <string>
#include <cstring>
#include <sstream>

namespace ExecUnitUtils
{
#ifdef _WIN32
    std::wstring utf8ToWString(const std::string& utf8);
    std::string  wStringToUtf8(const std::wstring& wstr);
#endif // _WIN32

    class TLV;
    using TLVPtr = std::shared_ptr<TLV>;

    class TLV
    {
    public:
        TLV();
        TLV(uint8_t typeIn, const std::vector<uint8_t>& dataIn);
        TLV(uint8_t typeIn, std::vector<uint8_t>&& dataIn);

        explicit TLV(uint8_t typeIn);

        uint8_t  getType() const noexcept { return m_type; }
        bool     isParent() const noexcept { return m_isParent; }
        uint32_t getFullSize() const noexcept { return m_fullSize; }

        bool load(const uint8_t* buffer, size_t bufferSize, size_t offset = 0);
        bool load(const std::vector<uint8_t>& buffer, size_t offset = 0)
        {
            return load(buffer.data(), buffer.size(), offset);
        }
        bool loadExact(
            const uint8_t* buffer,
            size_t bufferSize,
            size_t maxNodes = 4096u,
            size_t maxDepth = 64u);
        bool loadExact(
            const std::vector<uint8_t>& buffer,
            size_t maxNodes = 4096u,
            size_t maxDepth = 64u)
        {
            return loadExact(buffer.data(), buffer.size(), maxNodes, maxDepth);
        }

        bool addChild(const TLV& child);

        TLVPtr getChild(uint8_t childType, size_t idx = 0);
        const TLVPtr getChild(uint8_t childType, size_t idx = 0) const;

        size_t getChildCount(uint8_t childType) const;

        std::vector<uint8_t> getFullBuffer() const;

        bool getAsString(std::string& out) const;

#ifdef _WIN32
        bool getAsWString(std::wstring& out) const;
#endif // _WIN32

        void setFromString(uint8_t typeIn, const std::string& utf8);

#ifdef _WIN32
        void setFromWString(uint8_t typeIn, const std::wstring& wstr);
#endif // _WIN32

        bool getAsByte(uint8_t& out) const;
        bool getAsSByte(int8_t& out) const;
        bool getAsBool(bool& out) const;
        bool getAsInt16(int16_t& out) const;
        bool getAsUInt16(uint16_t& out) const;
        bool getAsInt32(int32_t& out) const;
        bool getAsUInt32(uint32_t& out) const;
        bool getAsInt64(int64_t& out) const;
        bool getAsUInt64(uint64_t& out) const;
        bool getAsSingle(float& out) const;
        bool getAsDouble(double& out) const;
        bool getAsBytes(std::vector<uint8_t>& out) const;

        std::string toString() const;

    private:
        uint8_t  m_type = 0;
        bool     m_isParent = false;
        uint32_t m_fullSize = 0;

        std::vector<uint8_t> m_data;
        std::unordered_map<uint8_t, std::vector<TLVPtr>> m_children;

        void addChildInternal(const TLVPtr& child);
        void writeFullBuffer(std::vector<uint8_t>& out) const;

        template <typename T>
        bool getIntegral(T& out) const
        {
            if (m_isParent || m_data.size() != sizeof(T))
                return false;

            T value{};
            std::memcpy(&value, m_data.data(), sizeof(T));
            out = value;
            return true;
        }

        void makeLeaf(uint8_t typeIn, const uint8_t* data, size_t length);
    };
} // namespace ExecUnitUtils
