#pragma once
#include <memory>
#include <mutex>
#include <vector>

typedef uint8_t UINT8;
typedef uint16_t UINT16;
typedef uint32_t UINT32;
typedef uint64_t UINT64;
typedef uint8_t* PUINT8;
typedef uint16_t* PUINT16;
typedef uint32_t* PUINT32;
typedef uint64_t* PUINT64;

typedef int32_t INT32;

typedef void* PVOID;
typedef unsigned char* PBYTE;

_Pragma("pack(push, 1)")
struct TLVheader
{
	UINT8 type;
	UINT32 length;
};
_Pragma("pack(pop)")
typedef TLVheader* PTLVheader;


#define TLV_PARENT_TYPE_FLAG 0x80

class TLV
{
	std::recursive_mutex io_mutex;
	UINT8 type = 0;
	UINT32 length = 0;
	bool parent = false;
	PVOID value = NULL;

	std::shared_ptr<TLV> child;
	std::shared_ptr<TLV> sibling;

	void clear();

public:
	TLV();
	TLV(UINT8 type);
	TLV(UINT8 type, std::vector<uint8_t> data);
	TLV(UINT8 type, PVOID data, UINT32 length);
	TLV(UINT8 type, std::string data);
	~TLV();

	bool load(std::vector<uint8_t>);
	bool load(PBYTE data, UINT32 length);

	UINT8 getType();
	UINT32 getValueLength();
	UINT32 getTotalLength();
	bool isParent();
	bool contains(UINT8 type);
	UINT32 count(UINT8 type);
	std::shared_ptr<TLV> getChild(UINT8 type);
	std::shared_ptr<TLV> getChild(UINT8 type, UINT32 idx);

	std::vector<uint8_t> getValue();
	bool getUInt8(UINT8& valueOut);
	bool getUInt16(UINT16& valueOut);
	bool getUInt32(UINT32& valueOut);
	bool getUInt64(UINT64& valueOut);
	UINT8 getUInt8();
	UINT16 getUInt16();
	UINT32 getUInt32();
	UINT64 getUInt64();
	std::string getStr();
	bool getStr(std::string& valueOut);
	bool getStr(std::string& valueOut, UINT32& lenOut);
	bool getBuffer(PVOID& valueOut, UINT32& lenOut);
	bool copyBuffer(PVOID valueOut, UINT32 lenOut);

	void addChild(std::shared_ptr<TLV> child);
	std::vector<uint8_t> genBytes();
};