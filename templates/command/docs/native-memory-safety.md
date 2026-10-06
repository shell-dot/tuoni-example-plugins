# Native C/C++ memory-safety review

Use this for ordinary C/C++ library code on Windows and Linux. These are review
priorities, not a diagnosis of a particular crash. Establish a failing input,
diagnostic, or ownership violation before claiming a cause. Compilation and
exception handling do not establish memory safety.

## Windows: no authored exceptions

**Hard requirement:** Project-authored Windows `native-lib` C++ code must not
throw or rethrow exceptions or use exceptions for error handling. This includes
project-owned helpers, callbacks, validation, diagnostics, and cleanup. Do not
deliberately raise Windows structured exceptions or replace failure handling
with process termination.

Report failures through explicit, checked status/results and deterministic
nonthrowing cleanup. Review potentially throwing operations such as allocation,
container growth, conversion, and worker creation as well as explicit `throw`
statements. Use documented nonthrowing failure paths for project-authored error
handling; absence of the `throw` keyword alone is not verification.

Defensive `try`/`catch` is permitted solely to contain exceptions originating in
dependencies or the runtime and translate them into checked failure results.
Existing exception-containment instructions serve this purpose; they do not
permit project-authored exceptions or rethrows.

Adding `noexcept` or disabling compiler exception support does not establish
that an operation cannot throw. An exception escaping a `noexcept` function
terminates the process. Verify the implementation and its failure paths instead
of using either setting as a substitute. Do not claim existing code complies
until it has been reviewed; this documentation change is not a code audit.

## Review before changing native code

For the functions being changed, identify each buffer's owner, valid byte count,
last user, and release operation. Include temporary values, callback captures,
views, error paths, and reused helpers. Review these common fault sources:

| Fault source | Questions to resolve in the code |
| --- | --- |
| Dangling pointers and borrowed views | Does a pointer refer to a local array, temporary string, parser-owned storage, or a container that can grow or be replaced? A saved `c_str()`, `data()`, iterator, or reference may become invalid after mutation. A callback capturing by reference does not extend the referenced object's lifetime. Retain an owner or make an owning copy before the data outlives its source. |
| Bounds and size arithmetic | Validate signed lengths before converting to unsigned. Validate offsets before subtracting them from available bytes, and check multiplication/addition before allocation or copying. A length field is not proof that those bytes exist. Check capacity in the destination as well as readable bytes in the source, including terminators. Check overlap before using copy APIs that require disjoint ranges. `vector::reserve()` does not create elements; indexing remains bounded by `size()`. |
| Empty buffers and strings | Never use element zero of an empty container. Establish the called API's pointer rules even when the length is zero; an empty-buffer pointer is not automatically valid for every API. Binary data is not a NUL-terminated string. Keep byte counts distinct from character counts, especially for UTF-16. Check conversions and truncation before passing sizes to narrower API parameters. |
| Allocation and release ownership | Pair each allocation with the required release API: `new/delete`, `new[]/delete[]`, `malloc/free`, or the library's own release function. Do not free borrowed storage or assume different library runtimes share an allocator. Check copy/move behavior of objects owning raw pointers or handles; accidental copies can double-release them. A failed reallocation must not lose the original owner. |
| Layout and type assumptions | Do not truncate pointers to 32-bit integers or assume `long` has the same width on 64-bit Windows and Linux. Casting external bytes to a struct does not establish alignment, object lifetime, padding, or byte order. Decode fields with documented widths and checked extents; copying bytes does not construct an arbitrary C++ object. Avoid passing C++ containers across incompatible binary interfaces. |
| Failed API calls and partially initialized state | Initialize local ownership state and check the documented success condition before reading output lengths, buffers, or handles. Never read an uninitialized value. Do not treat a failed call as valid empty input. Windows APIs differ between null and `INVALID_HANDLE_VALUE` failure values; POSIX descriptor zero is valid, whereas `-1` indicates failure. Release only successfully acquired resources, once, and invalidate the owning slot after release. |
| Races, callbacks, and destruction | An atomic stop flag does not protect a shared buffer or compound state. Establish synchronization for all shared accesses and retain state until its users finish. Unregistering a callback may not drain one already running. Review destruction order, self-join, and joining while holding a lock the worker needs. Sleeps and detached threads do not prove work has finished. |
| Exceptions, stack use, and diagnostics | Exceptions escaping a worker or a `noexcept` function can terminate the process; an exception escaping a destructor invoked during unwinding also terminates the process. Check partial construction and nonthrowing cleanup. Bound recursion and avoid input-sized stack arrays. Match variadic format arguments exactly, never use input as a format string, and avoid logging through stale pointers. Logging and error construction can allocate or throw too. |

A catch-all C++ handler does not make an invalid memory access recoverable.
Do not hide a failure with an empty catch, disable a diagnostic, or resume after
a memory-corruption fault. A crash in allocation, logging, or destruction may be
the later symptom of an earlier invalid write or race.

## Diagnose with isolated local tests

Exercise parsers, buffer handling, and ordinary object lifetimes in a disposable
local test process with synthetic data. Do not use a running agent as the crash
test harness. Begin with the smallest failing case and preserve its input,
compiler/architecture, build identity, symbols, and first diagnostic. Inspect the
allocation and release history as well as the final faulting line.

Use focused cases relevant to the changed function:

- Empty input, every relevant truncated prefix, declared length beyond available
  bytes, and values at and just beyond accepted limits. Verify rejection before
  allocation or access; testing an enormous length need not allocate that amount.
- Failure after each resource acquisition, errors during diagnostic construction,
  and repeated creation/destruction. Check remaining ownership after each case.
- Concurrent access, replacement of borrowed storage, and cancellation during
  local work when those paths exist. Use controlled interleavings rather than
  relying on sleep durations to expose lifetime errors.

Select diagnostics supported by the actual compiler and test platform:

- [Clang AddressSanitizer](https://clang.llvm.org/docs/AddressSanitizer.html)
  and [MSVC AddressSanitizer](https://learn.microsoft.com/en-us/cpp/sanitizers/asan)
  help find invalid accesses and allocation/lifetime errors. Instrumentation and
  runtime requirements must be checked for the chosen toolchain.
- [UndefinedBehaviorSanitizer](https://clang.llvm.org/docs/UndefinedBehaviorSanitizer.html)
  covers additional undefined behavior, such as selected arithmetic and alignment
  errors, where supported.
- Use [ThreadSanitizer](https://clang.llvm.org/docs/ThreadSanitizer.html) in a
  separate supported test configuration for data races. Do not assume it is
  available for every Windows/Linux compiler or architecture.

These tools are complementary and depend on the paths exercised. A clean run is
not proof that all lifetimes, races, or inputs are safe. Keep diagnostic builds
separate from distributable artifacts and follow the project's authorized build
route; tool availability does not authorize changing that route.

Record the suspected cause, reproducing case, observed diagnostic, and check
result in the existing project context. Distinguish source review, compilation,
and executed diagnostic tests, and name untested platforms or paths explicitly.
