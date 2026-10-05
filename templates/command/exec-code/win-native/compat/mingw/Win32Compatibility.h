#pragma once

#include <windows.h>

// Some MinGW winerror.h versions omit this Windows SDK constant.
// https://learn.microsoft.com/en-us/windows/win32/debug/system-error-codes--500-999-
#ifndef ERROR_UNHANDLED_EXCEPTION
#define ERROR_UNHANDLED_EXCEPTION 574L
#endif
