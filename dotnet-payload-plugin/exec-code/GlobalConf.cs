using System;
using System.IO;
using System.Reflection;

namespace DotNetAgent
{
    internal class GlobalConf
    {
        private const int PE_HEADER_OFFSET_LOCATION = 0x3C;
        private const int COFF_HEADER_SIZE = 20;
        private const int SECTION_HEADER_SIZE = 40;
        private const int SECTION_SIZE_OF_RAW_DATA_OFFSET = 16;
        private const int SECTION_POINTER_TO_RAW_DATA_OFFSET = 20;

        public static byte[] GetAddedSetupBuffer()
        {
            try
            {
                string exePath = Assembly.GetExecutingAssembly().Location;
                byte[] fileBytes = File.ReadAllBytes(exePath);

                int peHeaderOffset = BitConverter.ToInt32(fileBytes, PE_HEADER_OFFSET_LOCATION);

                int coffHeaderOffset = peHeaderOffset + 4;

                int numberOfSections = BitConverter.ToUInt16(fileBytes, coffHeaderOffset + 2);

                int sizeOfOptionalHeader = BitConverter.ToUInt16(fileBytes, coffHeaderOffset + 16);

                int sectionHeadersOffset = coffHeaderOffset + COFF_HEADER_SIZE + sizeOfOptionalHeader;

                int peEndOffset = 0;
                for (int i = 0; i < numberOfSections; i++)
                {
                    int sectionOffset = sectionHeadersOffset + (i * SECTION_HEADER_SIZE);
                    int sizeOfRawData = BitConverter.ToInt32(fileBytes, sectionOffset + SECTION_SIZE_OF_RAW_DATA_OFFSET);
                    int pointerToRawData = BitConverter.ToInt32(fileBytes, sectionOffset + SECTION_POINTER_TO_RAW_DATA_OFFSET);
                    int sectionEnd = pointerToRawData + sizeOfRawData;
                    if (sectionEnd > peEndOffset)
                        peEndOffset = sectionEnd;
                }

                if (peEndOffset >= fileBytes.Length)
                    return new byte[0];
                byte[] setupBuffer = new byte[fileBytes.Length - peEndOffset];
                Array.Copy(fileBytes, peEndOffset, setupBuffer, 0, setupBuffer.Length);

                return setupBuffer;
            }
            catch (Exception ex)
            {
                // Malformed PE or missing appended config results in empty buffer,
                // letting the agent start with no initial commands rather than crashing.
                Logger.Warning($"Failed to extract setup buffer from PE: {ex.Message}");
                return new byte[0];
            }
        }
    }
}
