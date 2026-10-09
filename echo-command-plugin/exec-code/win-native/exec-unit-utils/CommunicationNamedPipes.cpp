#ifdef _WIN32
#include "CommunicationNamedPipes.h"
#include <algorithm>
#include <chrono>
#include <cerrno>
#include <cstdio>
#include <cstring>
#include <exception>
#include <iostream>
#include <new>
#include <process.h>
#include <windows.h>

namespace ExecUnitUtils
{

    namespace
    {
        void setError(
            NamedPipeTransportError* error,
            NamedPipeFailureCategory category,
            DWORD windowsError,
            const char* text) noexcept
        {
            if (error == nullptr)
                return;
            error->clear();
            error->category = category;
            error->windowsError = static_cast<std::uint32_t>(windowsError);
            if (text != nullptr)
                (void)strncpy_s(error->text.data(), error->text.size(), text, _TRUNCATE);
        }

        class SrwExclusiveLock final
        {
        public:
            explicit SrwExclusiveLock(SRWLOCK& lock) noexcept : lock_(lock)
            {
                AcquireSRWLockExclusive(&lock_);
            }

            ~SrwExclusiveLock() noexcept
            {
                ReleaseSRWLockExclusive(&lock_);
            }

            SrwExclusiveLock(const SrwExclusiveLock&) = delete;
            SrwExclusiveLock& operator=(const SrwExclusiveLock&) = delete;

        private:
            SRWLOCK& lock_;
        };

        struct PendingIo final
        {
            explicit PendingIo(DWORD requestedSize) noexcept
                : size(requestedSize),
                buffer(static_cast<std::uint8_t*>(
                    HeapAlloc(GetProcessHeap(), 0, requestedSize))),
                completionEvent(CreateEventW(nullptr, TRUE, FALSE, nullptr))
            {
                overlapped.hEvent = completionEvent;
            }

            ~PendingIo() noexcept
            {
                if (completionEvent != nullptr)
                    (void)CloseHandle(completionEvent);
                if (buffer != nullptr)
                    (void)HeapFree(GetProcessHeap(), 0, buffer);
            }

            bool valid() const noexcept
            {
                return completionEvent != nullptr && buffer != nullptr;
            }

            OVERLAPPED overlapped{};
            DWORD size;
            std::uint8_t* buffer;
            HANDLE completionEvent;
        };

        PendingIo* createPendingIo(DWORD size) noexcept
        {
            void* storage = HeapAlloc(GetProcessHeap(), 0, sizeof(PendingIo));
            if (storage == nullptr)
                return nullptr;
            PendingIo* operation = new (storage) PendingIo(size);
            if (!operation->valid())
            {
                operation->~PendingIo();
                (void)HeapFree(GetProcessHeap(), 0, storage);
                return nullptr;
            }
            return operation;
        }

        void destroyPendingIo(PendingIo*& operation) noexcept
        {
            if (operation == nullptr)
                return;
            void* storage = operation;
            operation->~PendingIo();
            (void)HeapFree(GetProcessHeap(), 0, storage);
            operation = nullptr;
        }

        void abandonPendingIo(PendingIo*& operation) noexcept
        {
            // The kernel may still access the OVERLAPPED and buffer after a
            // cancellation request. Intentionally release the heap allocation rather
            // than running cleanup code after the execunit DLL may be unloaded.
            // This path is reached only if cancellation itself did not complete
            // within the two-second close grace; closing the pipe handle still
            // terminates the kernel request.
            operation = nullptr;
        }

        void cancelAndReapPendingIo(
            HANDLE h,
            PendingIo*& operation,
            int closeTimeoutMs) noexcept
        {
            // Cancel exactly the request whose OVERLAPPED storage is owned by
            // operation. A process-wide or handle-wide cancellation performed by
            // dispose() is not sufficient here: the shutdown event may be signaled
            // independently, and returning while this request is still pending would
            // let the kernel access freed OVERLAPPED/buffer storage.
            if (operation == nullptr)
                return;
            (void)CancelIoEx(h, &operation->overlapped);
            if (WaitForSingleObject(
                    operation->completionEvent,
                    static_cast<DWORD>(closeTimeoutMs)) == WAIT_OBJECT_0)
            {
                DWORD ignored = 0;
                (void)GetOverlappedResult(
                    h, &operation->overlapped, &ignored, FALSE);
                return;
            }

            // Preserve the request storage if a broken or closing handle does not
            // report completion within the configured grace. The owning handle is
            // closed by dispose(), which terminates the kernel request; leaking this
            // exceptional allocation is safer than freeing live OVERLAPPED memory.
            abandonPendingIo(operation);
        }

        // Overlapped synchronous-style I/O: the handle is opened with FILE_FLAG_OVERLAPPED
        // so concurrent reads on the listener thread and writes on the main thread don't
        // serialize at the handle level (which would deadlock). Each request owns a
        // heap-backed OVERLAPPED and buffer, so a timed-out request can outlive its caller
        // without Windows accessing dead stack storage.
        bool waitForIo(
            HANDLE h,
            HANDLE shutdownEvent,
            PendingIo*& operation,
            DWORD& transferred,
            int timeoutMs,
            int closeTimeoutMs,
            DWORD& failureError) noexcept
        {
            DWORD waitTime = timeoutMs < 0 ? INFINITE : static_cast<DWORD>(timeoutMs);
            HANDLE events[] = { operation->completionEvent, shutdownEvent };
            DWORD waitResult = WaitForMultipleObjects(2, events, FALSE, waitTime);
            if (waitResult == WAIT_OBJECT_0)
            {
                if (GetOverlappedResult(
                        h, &operation->overlapped, &transferred, FALSE) != FALSE)
                    return true;
                failureError = GetLastError();
                return false;
            }

            if (waitResult == WAIT_OBJECT_0 + 1)
            {
                failureError = ERROR_OPERATION_ABORTED;
                cancelAndReapPendingIo(h, operation, closeTimeoutMs);
                return false;
            }

            // A frame deadline or wait failure cancels only this request. Give Windows
            // the bounded close grace to finish cancellation, then transfer lifetime
            // ownership to an intentional leak rather than blocking indefinitely.
            failureError = waitResult == WAIT_TIMEOUT ? ERROR_TIMEOUT : GetLastError();
            cancelAndReapPendingIo(h, operation, closeTimeoutMs);
            return false;
        }

        class FrameDeadline final
        {
        public:
            FrameDeadline(int firstByteTimeoutMs, int partialTimeoutMs)
                : partialTimeoutMs_(partialTimeoutMs),
                deadline_(makeDeadline(firstByteTimeoutMs))
            {
            }

            int remaining() const
            {
                if (deadline_ == (TimePoint::max)())
                    return -1;
                const auto now = Clock::now();
                if (now >= deadline_)
                    return 0;
                const auto remaining = std::chrono::duration_cast<
                    std::chrono::milliseconds>(deadline_ - now);
                const auto rounded = remaining + std::chrono::milliseconds(1);
                if (rounded.count() > (std::numeric_limits<int>::max)())
                    return (std::numeric_limits<int>::max)();
                return static_cast<int>(rounded.count());
            }

            void onBytesReceived()
            {
                if (receivedAny_)
                    return;
                receivedAny_ = true;
                const TimePoint partialDeadline = makeDeadline(partialTimeoutMs_);
                if (deadline_ == (TimePoint::max)()
                    || (partialDeadline != (TimePoint::max)()
                        && partialDeadline < deadline_))
                {
                    deadline_ = partialDeadline;
                }
            }

        private:
            using Clock = std::chrono::steady_clock;
            using TimePoint = Clock::time_point;

            static TimePoint makeDeadline(int timeoutMs)
            {
                if (timeoutMs < 0)
                    return (TimePoint::max)();
                return Clock::now() + std::chrono::milliseconds(timeoutMs);
            }

            int partialTimeoutMs_;
            TimePoint deadline_;
            bool receivedAny_ = false;
        };

        bool readExactWin(
            HANDLE h,
            HANDLE shutdownEvent,
            void* buffer,
            DWORD totalBytes,
            FrameDeadline& deadline,
            int closeTimeoutMs,
            DWORD& failureError) noexcept
        {
            auto* buf = static_cast<std::uint8_t*>(buffer);
            DWORD totalRead = 0;
            while (totalRead < totalBytes)
            {
                PendingIo* operation = createPendingIo(totalBytes - totalRead);
                if (operation == nullptr)
                {
                    failureError = ERROR_NOT_ENOUGH_MEMORY;
                    return false;
                }
                DWORD bytesRead = 0;
                BOOL ok = ReadFile(
                    h,
                    operation->buffer,
                    operation->size,
                    &bytesRead,
                    &operation->overlapped);
                if (!ok)
                {
                    DWORD err = GetLastError();
                    if (err == ERROR_IO_PENDING)
                    {
                        if (!waitForIo(
                                h,
                                shutdownEvent,
                                operation,
                                bytesRead,
                                deadline.remaining(),
                                closeTimeoutMs,
                                failureError))
                        {
                            destroyPendingIo(operation);
                            return false;
                        }
                    }
                    else
                    {
                        failureError = err;
                        destroyPendingIo(operation);
                        return false;
                    }
                }
                if (bytesRead == 0 || bytesRead > operation->size)
                {
                    failureError = bytesRead == 0 ? ERROR_BROKEN_PIPE : ERROR_INVALID_DATA;
                    destroyPendingIo(operation);
                    return false;
                }
                std::memcpy(buf + totalRead, operation->buffer, bytesRead);
                totalRead += bytesRead;
                deadline.onBytesReceived();
                destroyPendingIo(operation);
            }
            return true;
        }

        bool writeExactWin(
            HANDLE h,
            HANDLE shutdownEvent,
            const void* buffer,
            DWORD totalBytes,
            FrameDeadline& deadline,
            int closeTimeoutMs,
            DWORD& failureError) noexcept
        {
            auto* buf = static_cast<const std::uint8_t*>(buffer);
            DWORD totalWritten = 0;
            while (totalWritten < totalBytes)
            {
                PendingIo* operation = createPendingIo(totalBytes - totalWritten);
                if (operation == nullptr)
                {
                    failureError = ERROR_NOT_ENOUGH_MEMORY;
                    return false;
                }
                std::memcpy(
                    operation->buffer,
                    buf + totalWritten,
                    operation->size);
                DWORD bytesWritten = 0;
                BOOL ok = WriteFile(
                    h,
                    operation->buffer,
                    operation->size,
                    &bytesWritten,
                    &operation->overlapped);
                if (!ok)
                {
                    DWORD err = GetLastError();
                    if (err == ERROR_IO_PENDING)
                    {
                        if (!waitForIo(
                                h,
                                shutdownEvent,
                                operation,
                                bytesWritten,
                                deadline.remaining(),
                                closeTimeoutMs,
                                failureError))
                        {
                            destroyPendingIo(operation);
                            return false;
                        }
                    }
                    else
                    {
                        failureError = err;
                        destroyPendingIo(operation);
                        return false;
                    }
                }
                if (bytesWritten == 0 || bytesWritten > operation->size)
                {
                    failureError = bytesWritten == 0 ? ERROR_BROKEN_PIPE : ERROR_INVALID_DATA;
                    destroyPendingIo(operation);
                    return false;
                }
                totalWritten += bytesWritten;
                destroyPendingIo(operation);
            }
            return true;
        }
    } // anonymous namespace

    CommunicationNamedPipes::CommunicationNamedPipes(
        const char* pipeName,
        const CommunicationNamedPipesOptions& options)
        : _active(false),
        _cancelRequested(false),
        _seqNr(1),
        _options(options),
        _optionsValid(options.valid()),
        _handle(INVALID_HANDLE_VALUE),
        _shutdownEvent(CreateEventW(nullptr, TRUE, FALSE, nullptr)),
        _listenThreadHandle(nullptr),
        _listenerThreadId(0),
        _sendLock(SRWLOCK_INIT),
        _disposeLock(SRWLOCK_INIT),
        _joinLock(SRWLOCK_INIT),
        _pipeName(pipeName == nullptr ? "" : pipeName)
    {
        if (!_pipeName.empty() && _pipeName.rfind("\\\\", 0) != 0) {
            _pipeName = "\\\\.\\pipe\\" + _pipeName;
        }
    }

    CommunicationNamedPipes::~CommunicationNamedPipes() noexcept
    {
        if (_listenerThreadId.load() == GetCurrentThreadId()
            && _listenThreadHandle.load() != nullptr)
        {
            // Destruction from inside a callback cannot complete safely: returning
            // to listenForMessages() would access freed object state, while waiting
            // for the current thread would deadlock. End only this listener thread.
            // The allocation is intentionally left to its external owner; structured
            // commands never destroy their channel from a callback.
            _active.store(false);
            _cancelRequested.store(true);
            if (_shutdownEvent != nullptr)
                (void)SetEvent(_shutdownEvent);
            _endthreadex(ERROR_INVALID_OPERATION);
        }
        (void)dispose();
        if (_shutdownEvent != nullptr)
        {
            (void)CloseHandle(_shutdownEvent);
            _shutdownEvent = nullptr;
        }
    }

    std::vector<std::uint8_t> CommunicationNamedPipes::connect(int timeoutMs)
    {
        std::vector<std::uint8_t> result;
        (void)TryConnect(result, nullptr, timeoutMs);
        return result;
    }

    bool CommunicationNamedPipes::TryConnect(
        std::vector<std::uint8_t>& result,
        NamedPipeTransportError* error,
        int timeoutMs)
    {
        result.clear();
        if (error != nullptr)
            error->clear();

        if (_active.load()) {
            setError(error, NamedPipeFailureCategory::Validation,
                ERROR_ALREADY_INITIALIZED, "named-pipe channel is already connected");
            return false;
        }

        if (!_optionsValid || timeoutMs < -1 || _pipeName.empty()) {
            setError(error, NamedPipeFailureCategory::Validation,
                ERROR_INVALID_PARAMETER, "invalid named-pipe transport configuration");
            return false;
        }

        if (_shutdownEvent == nullptr) {
            setError(error, NamedPipeFailureCategory::Windows,
                ERROR_INVALID_HANDLE, "named-pipe shutdown event is unavailable");
            return false;
        }
        if (ResetEvent(_shutdownEvent) == FALSE)
        {
            const DWORD failure = GetLastError();
            setError(error, NamedPipeFailureCategory::Windows,
                failure, "could not reset named-pipe shutdown event");
            return false;
        }

        const ULONGLONG startTick = GetTickCount64();
        const std::string& pipeName = _pipeName;

        while (true) {
            HANDLE openedHandle = CreateFileA(
                pipeName.c_str(),
                GENERIC_READ | GENERIC_WRITE,
                0,
                nullptr,
                OPEN_EXISTING,
                FILE_FLAG_OVERLAPPED,
                nullptr);

            if (openedHandle != INVALID_HANDLE_VALUE) {
                _handle.store(openedHandle);
                break;
            }

            DWORD err = GetLastError();
            if (err != ERROR_PIPE_BUSY
                && err != ERROR_FILE_NOT_FOUND
                && err != ERROR_PATH_NOT_FOUND) {
                setError(error, NamedPipeFailureCategory::Windows,
                    err, "could not open named pipe");
                return false;
            }

            const ULONGLONG elapsed = GetTickCount64() - startTick;
            if (timeoutMs >= 0
                && elapsed >= static_cast<ULONGLONG>(timeoutMs)) {
                setError(error, NamedPipeFailureCategory::Timeout,
                    ERROR_TIMEOUT, "named-pipe connection timed out");
                return false;
            }

            DWORD waitMilliseconds = 25u;
            if (timeoutMs >= 0)
            {
                const ULONGLONG remaining =
                    static_cast<ULONGLONG>(timeoutMs) - elapsed;
                waitMilliseconds = static_cast<DWORD>((std::min)(
                    remaining, static_cast<ULONGLONG>(waitMilliseconds)));
            }
            if (WaitForSingleObject(_shutdownEvent, waitMilliseconds)
                != WAIT_TIMEOUT)
            {
                setError(error, NamedPipeFailureCategory::Canceled,
                    ERROR_OPERATION_ABORTED, "named-pipe connection was canceled");
                return false;
            }
        }

        DWORD mode = PIPE_READMODE_BYTE;
        if (SetNamedPipeHandleState(_handle.load(), &mode, nullptr, nullptr) == FALSE)
        {
            const DWORD failure = GetLastError();
            setError(error, NamedPipeFailureCategory::Windows,
                failure, "could not configure named-pipe mode");
            (void)dispose();
            return false;
        }

        _active = true;
        _cancelRequested = false;

        std::vector<std::uint8_t> initialData;
        int initialTimeout = _options.initialReadTimeoutMs;
        if (_options.connectDeadlineIncludesInitialFrame && timeoutMs >= 0)
        {
            const ULONGLONG elapsed = GetTickCount64() - startTick;
            const int remaining = elapsed >= static_cast<ULONGLONG>(timeoutMs)
                ? 0
                : timeoutMs - static_cast<int>(elapsed);
            if (initialTimeout < 0 || remaining < initialTimeout)
                initialTimeout = remaining;
        }
        if (!getData(initialData, true, initialTimeout, error)) {
            (void)dispose();
            return false;
        }

		TLV tlv;
        const bool parsed = _options.exactEnvelopes
            ? tlv.loadExact(initialData)
            : tlv.load(initialData, 0);
        if (!parsed || tlv.isParent()) {
            setError(error, NamedPipeFailureCategory::Validation,
                ERROR_INVALID_DATA, "initial named-pipe frame is not one exact leaf TLV");
            (void)dispose();
            return false;
        }
        std::vector<std::uint8_t> tlvData;
        if (!tlv.getAsBytes(tlvData))
        {
            setError(error, NamedPipeFailureCategory::Validation,
                ERROR_INVALID_DATA, "initial named-pipe TLV payload is invalid");
            (void)dispose();
            return false;
        }

        unsigned threadId = 0;
        const uintptr_t threadValue = _beginthreadex(
            nullptr, 0, &CommunicationNamedPipes::listenThreadEntry,
            this, 0, &threadId);
        if (threadValue == 0u)
        {
            const DWORD failure = errno == EAGAIN
                ? ERROR_MAX_THRDS_REACHED
                : ERROR_NOT_ENOUGH_MEMORY;
            setError(error, NamedPipeFailureCategory::Internal,
                failure, "could not start named-pipe listener thread");
            (void)dispose();
            return false;
        }
        _listenerThreadId.store(static_cast<DWORD>(threadId));
        _listenThreadHandle.store(reinterpret_cast<HANDLE>(threadValue));

        result.swap(tlvData);
        return true;
    }

    bool CommunicationNamedPipes::TryClose(NamedPipeTransportError* error) noexcept
    {
        return dispose(error);
    }

    void CommunicationNamedPipes::close() noexcept
    {
        (void)dispose();
    }

    unsigned __stdcall CommunicationNamedPipes::listenThreadEntry(void* context) noexcept
    {
        CommunicationNamedPipes* self =
            static_cast<CommunicationNamedPipes*>(context);
        if (self == nullptr)
            return ERROR_INVALID_PARAMETER;
        while (self->_listenThreadHandle.load() == nullptr
            && self->_active.load())
        {
            (void)SwitchToThread();
        }
        if (!self->_active.load())
        {
            self->_listenerThreadId.store(0);
            return ERROR_OPERATION_ABORTED;
        }
        try
        {
            self->listenForMessages();
        }
        catch (...)
        {
            self->_active.store(false);
            self->_listenerThreadId.store(0);
            return ERROR_UNHANDLED_EXCEPTION;
        }
        return ERROR_SUCCESS;
    }

    bool CommunicationNamedPipes::handleIncomingData(TLVPtr& tlv)
    {
        return false;
    }

    void CommunicationNamedPipes::listenForMessages()
    {
        _listenerThreadId.store(GetCurrentThreadId());
        while (_active.load() && !_cancelRequested.load()) {
            try
            {
                std::vector<std::uint8_t> data;
                if (!getData(data, false)) {
                    break;
                }

                if (data.empty()) {
                    continue;
                }

                TLVPtr tlv = std::make_shared<TLV>();

                const bool parsed = _options.exactEnvelopes
                    ? tlv->loadExact(data)
                    : tlv->load(data, 0);
                if (!parsed) {
                    if (_options.exactEnvelopes)
                    {
                        _active = false;
                        break;
                    }
                    continue;
                }

                // 0x3A = request/response with seq number. Route to waiter instead of callback.
                if (tlv->getType() == 0x3A) {
                    if (!tlv->isParent() || tlv->getChildCount(0x2) != 1u)
                    {
                        if (_options.exactEnvelopes)
                        {
                            _active = false;
                            break;
                        }
                        continue;
                    }
                    TLVPtr seqChild = tlv->getChild(0x2);
                    int32_t seq = 0;
                    if (seqChild && seqChild->getAsInt32(seq)) {
                        if (!_options.allowRequestResponses)
                            continue;
                        std::shared_ptr<std::condition_variable> cv;
                        {
                            std::lock_guard<std::mutex> lock(_responsesLock);
                            auto it = _signals.find(seq);
                            if (it != _signals.end()
                                && _responses.find(seq) == _responses.end())
                            {
                                _responses.emplace(seq, tlv);
                                cv = it->second;
                            }
                        }
                        if (cv)
                            cv->notify_all();
                        continue;
                    }
                    if (_options.exactEnvelopes)
                    {
                        _active = false;
                        break;
                    }
                    continue;
                }

                handleIncomingData(tlv);
            }
            catch (...)
            {
                _active = false;
                break;
            }
        }

        // Structured commands disable request/response messages and therefore do
        // not touch the potentially throwing C++ condition-variable path.
        if (_options.allowRequestResponses)
        {
            try
            {
                std::lock_guard<std::mutex> lock(_responsesLock);
                for (auto& kv : _signals)
                    kv.second->notify_all();
            }
            catch (...)
            {
                // Last-resort containment for the legacy credential-response path.
            }
        }
        _listenerThreadId.store(0);
    }

    TLVPtr CommunicationNamedPipes::waitForResponseTLV(int32_t seq, int timeoutMs)
    {
        std::unique_lock<std::mutex> lock(_responsesLock);

        auto found = _responses.find(seq);
        if (found != _responses.end()) {
            TLVPtr tlv = found->second;
            _responses.erase(found);
            _signals.erase(seq);
            return tlv;
        }
        if (!_options.allowRequestResponses)
            return nullptr;

        std::shared_ptr<std::condition_variable> cv;
        auto signal = _signals.find(seq);
        if (signal != _signals.end())
        {
            cv = signal->second;
        }
        else
        {
            if (_signals.size() >= _options.maxPendingResponses)
                return nullptr;
            cv = std::make_shared<std::condition_variable>();
            _signals.emplace(seq, cv);
        }

        const auto deadline = timeoutMs < 0
            ? (std::chrono::steady_clock::time_point::max)()
            : std::chrono::steady_clock::now() + std::chrono::milliseconds(timeoutMs);
        while (true) {
            if (!_active.load()) {
                _signals.erase(seq);
                return nullptr;
            }
            bool timedOut = false;
            if (timeoutMs < 0)
                cv->wait(lock);
            else
                timedOut = cv->wait_until(lock, deadline) == std::cv_status::timeout;
            if (timedOut) {
                _signals.erase(seq);
                return nullptr;
            }
            auto it = _responses.find(seq);
            if (it != _responses.end()) {
                TLVPtr tlv = it->second;
                _responses.erase(it);
                _signals.erase(seq);
                return tlv;
            }
            // Pipe closed while waiting: bail out.
            if (!_active.load()) {
                _signals.erase(seq);
                return nullptr;
            }
        }
    }

    std::pair<std::string, std::string> CommunicationNamedPipes::getCurrentCredentials(int timeoutMs)
    {
        std::pair<std::string, std::string> empty;
        if (!_active.load() || !_options.allowRequestResponses)
            return empty;

        int32_t seq = _seqNr.fetch_add(1);
        {
            std::lock_guard<std::mutex> lock(_responsesLock);
            if (_signals.size() >= _options.maxPendingResponses)
                return empty;
            _signals.emplace(seq, std::make_shared<std::condition_variable>());
        }

        // Build: parent TLV type 0x3A with children 0x1 = {0x01}, 0x2 = int32(seq)
        TLV request(0x3A);
        std::vector<std::uint8_t> flag{ 0x01 };
        TLV flagChild(0x1, flag);
        request.addChild(flagChild);

        std::vector<std::uint8_t> seqBytes(4);
        seqBytes[0] = (std::uint8_t)(seq & 0xFF);
        seqBytes[1] = (std::uint8_t)((seq >> 8) & 0xFF);
        seqBytes[2] = (std::uint8_t)((seq >> 16) & 0xFF);
        seqBytes[3] = (std::uint8_t)((seq >> 24) & 0xFF);
        TLV seqChild(0x2, seqBytes);
        request.addChild(seqChild);

        if (!putData(request.getFullBuffer()))
        {
            std::lock_guard<std::mutex> lock(_responsesLock);
            _signals.erase(seq);
            return empty;
        }

        TLVPtr response = waitForResponseTLV(seq, timeoutMs);
        if (!response)
            return empty;

        // C# reads credentials from response.getChild(0x4) which itself holds
        // child 0x1 (username) and child 0x2 (password).
        TLVPtr creds = response->getChild(0x4);
        if (!creds)
            return empty;

        TLVPtr userTlv = creds->getChild(0x1);
        TLVPtr passTlv = creds->getChild(0x2);
        if (!userTlv || !passTlv)
            return empty;

        std::string user, pass;
        userTlv->getAsString(user);
        passTlv->getAsString(pass);
        return std::make_pair(user, pass);
    }

    bool CommunicationNamedPipes::getData(
        std::vector<std::uint8_t>& outData,
        bool initialFrame,
        int initialTimeoutOverrideMs,
        NamedPipeTransportError* error)
    {
        outData.clear();
        if (error != nullptr)
            error->clear();

        if (!_active.load()) {
            setError(error, NamedPipeFailureCategory::Transport,
                ERROR_INVALID_STATE, "named-pipe channel is not active");
            return false;
        }

        HANDLE h = _handle.load();
        if (h == INVALID_HANDLE_VALUE) {
            setError(error, NamedPipeFailureCategory::Transport,
                ERROR_INVALID_HANDLE, "named-pipe handle is unavailable");
            return false;
        }

        try
        {
            std::uint32_t len = 0;
            const int initialTimeout =
                initialTimeoutOverrideMs == (std::numeric_limits<int>::min)()
                    ? _options.initialReadTimeoutMs
                    : initialTimeoutOverrideMs;
            FrameDeadline deadline(
                initialFrame ? initialTimeout : -1,
                _options.partialReadTimeoutMs);
            DWORD failure = ERROR_SUCCESS;
            if (!readExactWin(
                    h,
                    _shutdownEvent,
                    &len,
                    static_cast<DWORD>(sizeof(len)),
                    deadline,
                    _options.closeTimeoutMs,
                    failure)) {
                _active = false;
                setError(error,
                    failure == ERROR_TIMEOUT
                        ? NamedPipeFailureCategory::Timeout
                        : failure == ERROR_OPERATION_ABORTED
                            ? NamedPipeFailureCategory::Canceled
                        : NamedPipeFailureCategory::Transport,
                    failure, "could not read named-pipe frame length");
                return false;
            }

            if (len == 0) {
                if (_options.rejectEmptyFrames) {
                    _active = false;
                    setError(error, NamedPipeFailureCategory::Validation,
                        ERROR_INVALID_DATA, "empty named-pipe frame is not permitted");
                    return false;
                }
                return true;
            }

            if (len > _options.maxInboundFrameBytes) {
                _active = false;
                setError(error, NamedPipeFailureCategory::Limit,
                    ERROR_FILE_TOO_LARGE, "named-pipe frame exceeds configured limit");
                return false;
            }

            outData.resize(len);
            if (!readExactWin(
                    h,
                    _shutdownEvent,
                    outData.data(),
                    static_cast<DWORD>(len),
                    deadline,
                    _options.closeTimeoutMs,
                    failure)) {
                _active = false;
                outData.clear();
                setError(error,
                    failure == ERROR_TIMEOUT
                        ? NamedPipeFailureCategory::Timeout
                        : failure == ERROR_OPERATION_ABORTED
                            ? NamedPipeFailureCategory::Canceled
                        : NamedPipeFailureCategory::Transport,
                    failure, "could not read complete named-pipe frame");
                return false;
            }

            return true;
        }
        catch (const std::exception&)
        {
            _active = false;
            outData.clear();
            setError(error, NamedPipeFailureCategory::Internal,
                ERROR_NOT_ENOUGH_MEMORY, "could not allocate named-pipe input buffer");
            return false;
        }
    }

    bool CommunicationNamedPipes::putData(const std::vector<std::uint8_t>& data)
    {
        return TrySend(data, nullptr);
    }

    bool CommunicationNamedPipes::TrySend(
        const std::vector<std::uint8_t>& data,
        NamedPipeTransportError* error)
    {
        if (error != nullptr)
            error->clear();
        SrwExclusiveLock lock(_sendLock);

        if (!_active.load()) {
            setError(error, NamedPipeFailureCategory::Transport,
                ERROR_INVALID_STATE, "named-pipe channel is not active");
            return false;
        }

        if (data.size() > (std::numeric_limits<std::uint32_t>::max)()) {
            setError(error, NamedPipeFailureCategory::Limit,
                ERROR_FILE_TOO_LARGE, "outbound named-pipe frame is too large");
            return false;
        }

        std::uint32_t len = static_cast<std::uint32_t>(data.size());

        HANDLE h = _handle.load();
        if (h == INVALID_HANDLE_VALUE) {
            setError(error, NamedPipeFailureCategory::Transport,
                ERROR_INVALID_HANDLE, "named-pipe handle is unavailable");
            return false;
        }

        try
        {
            FrameDeadline deadline(
                _options.writeTimeoutMs,
                _options.writeTimeoutMs);
            DWORD failure = ERROR_SUCCESS;
            if (!writeExactWin(
                    h,
                    _shutdownEvent,
                    &len,
                    static_cast<DWORD>(sizeof(len)),
                    deadline,
                    _options.closeTimeoutMs,
                    failure)) {
                _active = false;
                setError(error,
                    failure == ERROR_TIMEOUT
                        ? NamedPipeFailureCategory::Timeout
                        : failure == ERROR_OPERATION_ABORTED
                            ? NamedPipeFailureCategory::Canceled
                        : NamedPipeFailureCategory::Transport,
                    failure, "could not write named-pipe frame length");
                return false;
            }

            if (!data.empty()) {
                if (!writeExactWin(
                        h,
                        _shutdownEvent,
                        data.data(),
                        static_cast<DWORD>(len),
                        deadline,
                        _options.closeTimeoutMs,
                        failure)) {
                    _active = false;
                    setError(error,
                        failure == ERROR_TIMEOUT
                            ? NamedPipeFailureCategory::Timeout
                            : failure == ERROR_OPERATION_ABORTED
                                ? NamedPipeFailureCategory::Canceled
                            : NamedPipeFailureCategory::Transport,
                        failure, "could not write complete named-pipe frame");
                    return false;
                }
            }

            return true;
        }
        catch (const std::exception&)
        {
            _active = false;
            setError(error, NamedPipeFailureCategory::Internal,
                ERROR_NOT_ENOUGH_MEMORY, "unexpected named-pipe send failure");
            return false;
        }
    }

    bool CommunicationNamedPipes::dispose(NamedPipeTransportError* error) noexcept
    {
        if (error != nullptr)
            error->clear();
        _cancelRequested.store(true);
        _active.store(false);

        if (_shutdownEvent != nullptr)
            (void)SetEvent(_shutdownEvent);

        bool success = true;
        HANDLE handle = _handle.load();
        {
            SrwExclusiveLock disposeLock(_disposeLock);
            handle = _handle.load();
            if (handle != INVALID_HANDLE_VALUE
                && CancelIoEx(handle, nullptr) == FALSE
                && GetLastError() != ERROR_NOT_FOUND)
            {
                const DWORD failure = GetLastError();
                setError(error, NamedPipeFailureCategory::Windows,
                    failure, "could not cancel named-pipe I/O");
                success = false;
            }
        }

        // Wake any pending getCurrentCredentials() waiters so they don't hang past close.
        if (_options.allowRequestResponses)
        {
            try
            {
                std::lock_guard<std::mutex> lock(_responsesLock);
                for (auto& kv : _signals)
                    kv.second->notify_all();
            }
            catch (...)
            {
                // Compatibility path only. Structured commands disable responses.
            }
        }

        if (_listenerThreadId.load() != GetCurrentThreadId())
        {
            SrwExclusiveLock joinLock(_joinLock);
            HANDLE listener = _listenThreadHandle.exchange(nullptr);
            if (listener != nullptr)
            {
                DWORD waitResult = WaitForSingleObject(
                    listener, static_cast<DWORD>(_options.closeTimeoutMs));
                if (waitResult == WAIT_TIMEOUT)
                {
                    // Listener completion is mandatory before an in-process DLL can
                    // return and be unloaded. CancelIoEx and the shutdown event make
                    // ordinary reads bounded; only user callback code can extend this.
                    waitResult = WaitForSingleObject(listener, INFINITE);
                }
                if (waitResult != WAIT_OBJECT_0)
                {
                    const DWORD failure = waitResult == WAIT_FAILED
                        ? GetLastError() : ERROR_GEN_FAILURE;
                    setError(error, NamedPipeFailureCategory::Windows,
                        failure, "could not join named-pipe listener thread");
                    success = false;
                }
                if (CloseHandle(listener) == FALSE)
                {
                    const DWORD failure = GetLastError();
                    setError(error, NamedPipeFailureCategory::Windows,
                        failure, "could not close named-pipe listener handle");
                    success = false;
                }
            }
        }

        handle = _handle.exchange(INVALID_HANDLE_VALUE);
        if (handle == INVALID_HANDLE_VALUE)
            return success;
        {
            SrwExclusiveLock disposeLock(_disposeLock);
            if (CloseHandle(handle) == FALSE)
            {
                const DWORD failure = GetLastError();
                setError(error, NamedPipeFailureCategory::Windows,
                    failure, "could not close named-pipe handle");
                success = false;
            }
        }
        return success;
    }

} // namespace ExecUnitUtils
#endif // _WIN32
