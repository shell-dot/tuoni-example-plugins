using System;
using System.IO;
using System.Runtime.InteropServices;
using System.Text;
using Microsoft.Win32.SafeHandles;

namespace DotNetAgent
{
    internal static class NativeCommandLsHelper
    {
        private const byte TLV_DIRECTORY = 0x1;
        private const byte TLV_FILE = 0x2;
        private const byte TLV_NAME = 0x1;
        private const byte TLV_FILE_SIZE = 0x2;
        private const byte TLV_CHILDREN = 0x3;
        private const byte TLV_CREATION_TIME = 0x4;
        private const byte TLV_LAST_ACCESS_TIME = 0x5;
        private const byte TLV_LAST_WRITE_TIME = 0x6;
        private const byte TLV_TARGET_PATH = 0x21;
        private const int MAX_PATH = 260;
        private const int MAX_FINAL_PATH_LENGTH = 32767;
        private const uint PMSF_DONT_STRIP_SPACES = 0x4;
        private const uint INVALID_FILE_ATTRIBUTES = 0xFFFFFFFF;
        private const uint FILE_FLAG_BACKUP_SEMANTICS = 0x02000000;
        private const string EXTENDED_UNC_PREFIX = @"\\?\UNC\";
        private const string EXTENDED_PREFIX = @"\\?\";

        private static readonly char[] PathSeparators = { '\\', '/' };
        private static readonly char[] WildcardChars = { '*', '?' };

        [DllImport("Shlwapi.dll", CharSet = CharSet.Unicode)]
        private static extern int PathMatchSpecExW(string pszName, string pszSpec, uint dwFlags);

        [DllImport("kernel32.dll", SetLastError = true, CharSet = CharSet.Unicode)]
        private static extern SafeFileHandle CreateFileW(
            string lpFileName,
            uint dwDesiredAccess,
            uint dwShareMode,
            IntPtr lpSecurityAttributes,
            uint dwCreationDisposition,
            uint dwFlagsAndAttributes,
            IntPtr hTemplateFile);

        [DllImport("kernel32.dll", SetLastError = true, CharSet = CharSet.Unicode)]
        private static extern uint GetFinalPathNameByHandleW(
            SafeFileHandle hFile,
            [Out] StringBuilder lpszFilePath,
            uint cchFilePath,
            uint dwFlags);

        public static bool ListDirFiles(string pathSpec, uint depth, TLV resultTlv, out string enumerationDirectory)
        {
            enumerationDirectory = null;

            try
            {
                if (!ParseInputPath(pathSpec, out string baseDirectory, out string selector))
                {
                    return false;
                }

                enumerationDirectory = baseDirectory;
                if (TryGetReparseTarget(baseDirectory, out string resolvedBaseDirectory) &&
                    HasDirectoryBit(GetFileAttributesSafe(resolvedBaseDirectory)))
                {
                    enumerationDirectory = resolvedBaseDirectory;
                }

                if (!ListDirFilesInternal(enumerationDirectory, selector, depth, resultTlv, true, out bool listMatched))
                {
                    return false;
                }

                return listMatched || HasWildcards(selector);
            }
            catch (Exception ex)
            {
                Logger.Warning($"ListDirFiles error: {ex.Message}");
                return false;
            }
        }

        private static bool ListDirFilesInternal(string directoryPath, string selector, uint depth, TLV resultTlv, bool isRoot, out bool matched)
        {
            matched = false;

            if (!Directory.Exists(directoryPath))
            {
                return !isRoot;
            }

            try
            {
                foreach (FileSystemInfo entry in new DirectoryInfo(directoryPath).EnumerateFileSystemInfos())
                {
                    bool entryMatches = EntryMatches(entry.Name, selector);

                    if ((entry.Attributes & FileAttributes.Directory) != 0)
                    {
                        string target = null;
                        string traversalPath = entry.FullName;
                        if ((entry.Attributes & FileAttributes.ReparsePoint) != 0 &&
                            (depth > 1 || entryMatches) &&
                            TryGetReparseTarget(entry.FullName, out target) &&
                            HasDirectoryBit(GetFileAttributesSafe(target)))
                        {
                            traversalPath = target;
                        }

                        TLV children = new TLV(TLV_CHILDREN);
                        bool childMatched = false;
                        if (depth > 1 && !ListDirFilesInternal(traversalPath, selector, depth - 1, children, false, out childMatched))
                        {
                            return false;
                        }

                        bool entryOrChildMatches = entryMatches || childMatched;
                        if (entryOrChildMatches)
                        {
                            resultTlv.AddChild(CreateDirectoryTlv((DirectoryInfo)entry, children, target));
                        }

                        matched = matched || entryOrChildMatches;
                    }
                    else if (entryMatches)
                    {
                        FileInfo fileEntry = (FileInfo)entry;
                        string target = null;
                        if ((fileEntry.Attributes & FileAttributes.ReparsePoint) != 0)
                        {
                            TryGetReparseTarget(fileEntry.FullName, out target);
                        }

                        resultTlv.AddChild(CreateFileTlv(fileEntry, target));
                        matched = true;
                    }
                }
            }
            catch (Exception ex)
            {
                Logger.Warning(isRoot
                    ? $"ListDirFiles root traversal error: {ex.Message}"
                    : $"ListDirFiles traversal error: {ex.Message}");
                return !isRoot;
            }

            return true;
        }

        private static bool EntryMatches(string fileName, string selector)
        {
            if (selector == "*" || string.IsNullOrEmpty(selector))
            {
                return true;
            }

            return PathMatchSpecExW(fileName, selector, PMSF_DONT_STRIP_SPACES) == 0;
        }

        private static TLV CreateFileTlv(FileInfo file, string target)
        {
            TLV fileTlv = new TLV(TLV_FILE);
            fileTlv.AddChild(new TLV(TLV_NAME, Encoding.UTF8.GetBytes(file.Name)));
            fileTlv.AddChild(new TLV(TLV_FILE_SIZE, BitConverter.GetBytes(file.Length)));
            AddTimestamps(fileTlv, file);
            AddTargetPath(fileTlv, target);
            return fileTlv;
        }

        private static TLV CreateDirectoryTlv(DirectoryInfo directory, TLV children, string target)
        {
            TLV dirTlv = new TLV(TLV_DIRECTORY);
            dirTlv.AddChild(new TLV(TLV_NAME, Encoding.UTF8.GetBytes(directory.Name)));
            dirTlv.AddChild(children);
            AddTimestamps(dirTlv, directory);
            AddTargetPath(dirTlv, target);
            return dirTlv;
        }

        private static void AddTimestamps(TLV tlv, FileSystemInfo info)
        {
            tlv.AddChild(new TLV(TLV_CREATION_TIME, BitConverter.GetBytes(ToUnixTimestamp(info.CreationTime))));
            tlv.AddChild(new TLV(TLV_LAST_ACCESS_TIME, BitConverter.GetBytes(ToUnixTimestamp(info.LastAccessTime))));
            tlv.AddChild(new TLV(TLV_LAST_WRITE_TIME, BitConverter.GetBytes(ToUnixTimestamp(info.LastWriteTime))));
        }

        private static void AddTargetPath(TLV tlv, string target)
        {
            if (!string.IsNullOrEmpty(target))
            {
                tlv.AddChild(new TLV(TLV_TARGET_PATH, Encoding.UTF8.GetBytes(target)));
            }
        }

        private static bool ParseInputPath(string pathSpec, out string baseDirectory, out string selector)
        {
            baseDirectory = null;
            selector = null;

            if (string.IsNullOrEmpty(pathSpec))
            {
                return false;
            }

            if (pathSpec[0] == '"' || pathSpec[pathSpec.Length - 1] == '"')
            {
                if (pathSpec.Length < 2 || pathSpec[0] != '"' || pathSpec[pathSpec.Length - 1] != '"')
                {
                    return false;
                }

                pathSpec = pathSpec.Substring(1, pathSpec.Length - 2);
                if (string.IsNullOrEmpty(pathSpec))
                {
                    return false;
                }
            }

            if (pathSpec.Length >= MAX_PATH)
            {
                return false;
            }

            bool trailingSeparator = IsPathSeparator(pathSpec[pathSpec.Length - 1]);
            uint attributes = GetFileAttributesSafe(pathSpec);
            SplitBaseAndSelector(
                pathSpec,
                trailingSeparator || (attributes != INVALID_FILE_ATTRIBUTES && HasDirectoryBit(attributes)),
                out string rawBaseDirectory,
                out string parsedSelector);

            if (string.IsNullOrEmpty(rawBaseDirectory) || string.IsNullOrEmpty(parsedSelector) ||
                HasWildcards(rawBaseDirectory))
            {
                return false;
            }

            try
            {
                baseDirectory = Path.GetFullPath(rawBaseDirectory);
            }
            catch
            {
                return false;
            }

            if (baseDirectory.Length >= MAX_PATH)
            {
                return false;
            }

            selector = parsedSelector;
            return true;
        }

        private static void SplitBaseAndSelector(string pathSpec, bool useWholePath, out string rawBaseDirectory, out string selector)
        {
            if (useWholePath)
            {
                rawBaseDirectory = pathSpec;
                selector = "*";
                return;
            }

            int separatorIndex = pathSpec.LastIndexOfAny(PathSeparators);
            if (separatorIndex != -1)
            {
                if (separatorIndex == 0)
                {
                    rawBaseDirectory = pathSpec.Length >= 3 ? pathSpec.Substring(0, 3) : pathSpec;
                }
                else if (separatorIndex == 2 && pathSpec[1] == ':')
                {
                    rawBaseDirectory = pathSpec.Substring(0, 3);
                }
                else
                {
                    rawBaseDirectory = pathSpec.Substring(0, separatorIndex);
                }

                selector = pathSpec.Substring(separatorIndex + 1);
            }
            else if (pathSpec.Length >= 2 && pathSpec[1] == ':')
            {
                rawBaseDirectory = pathSpec.Substring(0, 2);
                selector = pathSpec.Substring(2);
            }
            else
            {
                rawBaseDirectory = ".";
                selector = pathSpec;
            }
        }

        private static bool TryGetReparseTarget(string path, out string target)
        {
            target = null;

            using (SafeFileHandle handle = CreateFileW(
                path,
                0,
                (uint)(FileShare.ReadWrite | FileShare.Delete),
                IntPtr.Zero,
                (uint)FileMode.Open,
                FILE_FLAG_BACKUP_SEMANTICS,
                IntPtr.Zero))
            {
                if (handle.IsInvalid)
                {
                    return false;
                }

                StringBuilder pathBuffer = new StringBuilder(MAX_FINAL_PATH_LENGTH);
                uint pathLength = GetFinalPathNameByHandleW(handle, pathBuffer, (uint)pathBuffer.Capacity, 0);
                if (pathLength == 0 || pathLength >= (uint)pathBuffer.Capacity)
                {
                    return false;
                }

                target = pathBuffer.ToString(0, (int)pathLength);
            }

            string normalizedPath = NormalizeFinalPath(path);
            target = NormalizeFinalPath(target);
            if (target == null)
            {
                return false;
            }

            string comparablePath = ToComparablePath(normalizedPath);
            string comparableTarget = ToComparablePath(target);
            if (comparablePath == null || comparableTarget == null ||
                string.Equals(comparablePath, comparableTarget, StringComparison.OrdinalIgnoreCase))
            {
                target = null;
                return false;
            }

            return true;
        }

        private static string NormalizeFinalPath(string path)
        {
            if (string.IsNullOrEmpty(path))
            {
                return null;
            }

            if (path.StartsWith(EXTENDED_UNC_PREFIX, StringComparison.OrdinalIgnoreCase))
            {
                return @"\\" + path.Substring(EXTENDED_UNC_PREFIX.Length);
            }

            if (!path.StartsWith(EXTENDED_PREFIX, StringComparison.OrdinalIgnoreCase))
            {
                return path;
            }

            if (path.Length >= 6 &&
                IsDriveLetter(path[4]) &&
                path[5] == ':')
            {
                return path.Substring(EXTENDED_PREFIX.Length);
            }

            return null;
        }

        private static string ToComparablePath(string normalizedPath)
        {
            if (normalizedPath == null)
            {
                return null;
            }

            normalizedPath = normalizedPath.Replace('/', '\\');
            while (normalizedPath.Length > 3 && normalizedPath.EndsWith("\\"))
            {
                normalizedPath = normalizedPath.Substring(0, normalizedPath.Length - 1);
            }

            return IsAbsolutePath(normalizedPath) ? normalizedPath : null;
        }

        private static bool IsAbsolutePath(string path)
        {
            if (path.Length < 3)
            {
                return false;
            }

            return (IsDriveLetter(path[0]) && path[1] == ':' && IsPathSeparator(path[2])) ||
                (IsPathSeparator(path[0]) && IsPathSeparator(path[1]));
        }

        private static bool IsPathSeparator(char c)
        {
            return c == '\\' || c == '/';
        }

        private static bool HasWildcards(string value)
        {
            return value.IndexOfAny(WildcardChars) != -1;
        }

        private static bool IsDriveLetter(char c)
        {
            return (c >= 'A' && c <= 'Z') || (c >= 'a' && c <= 'z');
        }

        private static uint GetFileAttributesSafe(string path)
        {
            try
            {
                return (uint)File.GetAttributes(path);
            }
            catch
            {
                return INVALID_FILE_ATTRIBUTES;
            }
        }

        private static bool HasDirectoryBit(uint attributes)
        {
            return (attributes & (uint)FileAttributes.Directory) != 0;
        }

        private static long ToUnixTimestamp(DateTime dt)
        {
            return new DateTimeOffset(dt.ToUniversalTime()).ToUnixTimeSeconds();
        }
    }
}
