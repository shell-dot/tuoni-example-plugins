#pragma once
#include<windows.h>
#include<vector>
#include<string>

// RPC headers supply this alias in non-lean Windows builds. Keep the reference
// utility API available when WIN32_LEAN_AND_MEAN excludes those headers.
using byte = BYTE;

class Conversions
{
public:
#ifdef _WIN32
	static std::vector<byte> wstring2utf8(std::wstring input);
	static std::vector<byte> string2utf8(std::string input);
	static std::string wstring2string(std::wstring input);
	static std::wstring string2wstring(std::string input);
#endif // _WIN32
	static void decodeXOR(PVOID data, UINT32 size, UINT8 key) { for (UINT32 x = 0; x < size; x++) ((PUINT8)data)[x] ^= key; }
	static std::vector<byte> decodeXOR_PE(PVOID data, UINT32 size, UINT8 key);
};
