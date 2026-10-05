#pragma once
#include <winsock2.h>
#include <windows.h>

class CriticalSectionGuard
{
private:
    CRITICAL_SECTION& cs_;

public:
    explicit CriticalSectionGuard(CRITICAL_SECTION& cs) : cs_(cs)
    {
        EnterCriticalSection(&cs_);
    }

    ~CriticalSectionGuard()
    {
        LeaveCriticalSection(&cs_);
    }

    CriticalSectionGuard(const CriticalSectionGuard&) = delete;
    CriticalSectionGuard& operator=(const CriticalSectionGuard&) = delete;
};

class SocketHandle
{
private:
    SOCKET s_ = INVALID_SOCKET;

public:
    SocketHandle() = default;
    explicit SocketHandle(SOCKET s) : s_(s) {}

    ~SocketHandle()
    {
        reset();
    }

    SocketHandle(SocketHandle&& other) : s_(other.s_)
    {
        other.s_ = INVALID_SOCKET;
    }

    SocketHandle& operator=(SocketHandle&& other)    {
        if (this != &other)
        {
            reset();
            s_ = other.s_;
            other.s_ = INVALID_SOCKET;
        }
        return *this;
    }

    SocketHandle(const SocketHandle&) = delete;
    SocketHandle& operator=(const SocketHandle&) = delete;

    void reset(SOCKET s = INVALID_SOCKET)
    {
        if (s_ != INVALID_SOCKET)
            closesocket(s_);
        s_ = s;
    }

    SOCKET get() const { return s_; }
    explicit operator bool() const { return s_ != INVALID_SOCKET; }
};
