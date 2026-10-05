#include "Conversions.h"


#ifdef _WIN32
std::vector<byte> Conversions::wstring2utf8(std::wstring input)
{
    int utf8Length = WideCharToMultiByte(CP_UTF8, 0, input.c_str(), static_cast<int>(input.length()), nullptr, 0, nullptr, nullptr);
    if (utf8Length > 0)
    {
        std::vector<byte> output(utf8Length);
        WideCharToMultiByte(CP_UTF8, 0, input.c_str(), static_cast<int>(input.length()), (LPSTR)output.data(), utf8Length, nullptr, nullptr);
        return output;
    }
    return std::vector<byte>();
}

std::vector<byte> Conversions::string2utf8(std::string input)
{
    //TODO: This is actually not correct, but it's good enough for now
    std::vector<byte> output(input.length());
    memcpy(output.data(), input.c_str(), input.length());
    return output;
}

std::string Conversions::wstring2string(std::wstring input)
{
    int utf8Length = WideCharToMultiByte(CP_UTF8, 0, input.c_str(), static_cast<int>(input.length()), nullptr, 0, nullptr, nullptr);
    if (utf8Length > 0)
    {
        std::string output(utf8Length, '\0');
        WideCharToMultiByte(CP_UTF8, 0, input.c_str(), static_cast<int>(input.length()), (LPSTR)output.data(), utf8Length, nullptr, nullptr);
        return output;
    }
    return std::string();
}

std::wstring Conversions::string2wstring(std::string input)
{
    int wideLength = MultiByteToWideChar(CP_UTF8, 0, input.c_str(), static_cast<int>(input.length()), nullptr, 0);
    if (wideLength > 0)
    {
        std::wstring output(wideLength, L'\0');
        MultiByteToWideChar(CP_UTF8, 0, input.c_str(), static_cast<int>(input.length()), const_cast<LPWSTR>(output.c_str()), wideLength);
        return output;
    }
	return std::wstring();
}

#endif // _WIN32
