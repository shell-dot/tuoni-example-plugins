#pragma once
#include "Conversions.h"
#include <windows.h>
#include <mutex>
#include <vector>
#include <list>
#include <memory>
#include <cstring>

#ifdef _MSC_VER
#define PACK_STRUCT( __Declaration__ ) __pragma( pack(push, 1) ) __Declaration__ __pragma( pack(pop))
#else
#define PACK_STRUCT( __Declaration__ ) _Pragma("pack(push, 1)") __Declaration__ _Pragma("pack(pop)")
#endif

PACK_STRUCT(struct TLVheader
{
	UINT8 type;
	UINT32 length;
};);
typedef TLVheader* PTLVheader;

#define TLV_PARENT_TYPE_FLAG 0x80

class TLV;
using TLVPtr = std::shared_ptr<TLV>;

class TLV
{
protected:
	std::recursive_mutex io_mutex;
	UINT8 type = 0;
	bool parent = false;
	std::vector<byte> value;
	TLVPtr child;
	TLVPtr sibling;


	bool load_internal(PBYTE data, UINT32 inputLength);

public:
	TLV() {}
	template<typename T>
	TLV(UINT8 type, T& value);
	template<typename T>
	TLV(UINT8 type, T&& value);
	TLV(UINT8 type) : type(type), parent(true) {}
	TLV(UINT8 type, std::vector<byte>& data) : type(type), parent(false), value(data) {}
	TLV(UINT8 type, std::vector<byte>&& data) : type(type), parent(false), value(data) {}
#ifdef _WIN32
	TLV(UINT8 type, std::string data) : type(type), parent(false), value(Conversions::string2utf8(data)) {}
	TLV(UINT8 type, std::wstring data) : type(type), parent(false), value(Conversions::wstring2utf8(data)) {}
	TLV(UINT8 type, char* data) : type(type), parent(false), value(Conversions::string2utf8(data)) {}
	TLV(UINT8 type, wchar_t* data) : type(type), parent(false), value(Conversions::wstring2utf8(data)) {}
	TLV(UINT8 type, const char* data) : type(type), parent(false), value(Conversions::string2utf8(data)) {}
	TLV(UINT8 type, const wchar_t* data) : type(type), parent(false), value(Conversions::wstring2utf8(data)) {}
#else // _WIN32
	TLV(UINT8 type, std::string data) : type(type), parent(false), value(data.c_str(), data.c_str() + data.length()) {}
	TLV(UINT8 type, char* data) : type(type), parent(false), value(data, data + strlen(data)) {}
	TLV(UINT8 type, const char* data) : type(type), parent(false), value(data, data + strlen(data)) {}
#endif
	~TLV() noexcept;
	void clear() noexcept;

	bool load(const std::vector<byte>&& data);
	bool load(const std::vector<byte>& data);
	bool load(PBYTE data, UINT32 inputLength) { return load_internal(data, inputLength); }

	UINT8 getType() { return type; }
	UINT32 getValueLength();
	UINT32 getTotalLength();
	bool isParent() { return parent; }
	bool contains(UINT8 type);
	UINT32 count(UINT8 type);
	TLVPtr getChild(UINT8 type) { return getChild(type, 0); }
	TLVPtr getChild(UINT8 type, UINT32 idx);

	template<typename T>
	bool getValue(T& valueOut);
	bool getAsciiStr(std::string& valueOut);
	bool getUnicodeStr(std::wstring& valueOut);
	std::vector<byte> getBytes() { std::lock_guard<std::recursive_mutex> lk(io_mutex); return value; }
	std::vector<byte> genBytes();
	void addChild(std::shared_ptr<TLV> child);

};

#include "TLV.tpp"
