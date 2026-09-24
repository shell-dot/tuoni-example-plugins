using System;
using System.Runtime.InteropServices;
using System.Security.Cryptography;

namespace DotNetAgent
{
    internal class Encryption
    {
        private const int RSA_PKCS1_PADDING_OVERHEAD = 0x40;
        private const uint ERROR_SUCCESS = 0x00000000;
        private const string BCRYPT_AES_ALGORITHM = "AES";
        private const string BCRYPT_CHAINING_MODE = "ChainingMode";
        private const string BCRYPT_CHAIN_MODE_GCM = "ChainingModeGCM";
        private const int GCM_IV_SIZE = 12;
        private const int GCM_TAG_SIZE = 16;
        private const int AES_KEY_SIZE = 16;
        private const int AES_BLOCK_SIZE = 16;
        private const uint BCRYPT_AUTH_MODE_INFO_VERSION = 1;

        private static RSACryptoServiceProvider _rsa;
        private static byte[] _aesKey;
        private static IntPtr _hAesAlg = IntPtr.Zero;
        private static IntPtr _hAesKey = IntPtr.Zero;

        [StructLayout(LayoutKind.Sequential)]
        private struct BCRYPT_AUTHENTICATED_CIPHER_MODE_INFO
        {
            public uint cbSize;
            public uint dwInfoVersion;
            public IntPtr pbNonce;
            public uint cbNonce;
            public IntPtr pbAuthData;
            public uint cbAuthData;
            public IntPtr pbTag;
            public uint cbTag;
            public IntPtr pbMacContext;
            public uint cbMacContext;
            public uint cbAAD;
            public ulong cbData;
            public uint dwFlags;

            public static BCRYPT_AUTHENTICATED_CIPHER_MODE_INFO Create()
            {
                var info = new BCRYPT_AUTHENTICATED_CIPHER_MODE_INFO();
                info.cbSize = (uint)Marshal.SizeOf(typeof(BCRYPT_AUTHENTICATED_CIPHER_MODE_INFO));
                info.dwInfoVersion = BCRYPT_AUTH_MODE_INFO_VERSION;
                return info;
            }
        }

        [DllImport("bcrypt.dll", CharSet = CharSet.Unicode)]
        private static extern uint BCryptOpenAlgorithmProvider(
            out IntPtr phAlgorithm,
            string pszAlgId,
            string pszImplementation,
            uint dwFlags);

        [DllImport("bcrypt.dll", CharSet = CharSet.Unicode)]
        private static extern uint BCryptSetProperty(
            IntPtr hObject,
            string pszProperty,
            [MarshalAs(UnmanagedType.LPWStr)] string pbInput,
            int cbInput,
            uint dwFlags);

        [DllImport("bcrypt.dll")]
        private static extern uint BCryptGenerateSymmetricKey(
            IntPtr hAlgorithm,
            out IntPtr phKey,
            IntPtr pbKeyObject,
            int cbKeyObject,
            byte[] pbSecret,
            int cbSecret,
            uint dwFlags);

        [DllImport("bcrypt.dll")]
        private static extern uint BCryptEncrypt(
            IntPtr hKey,
            byte[] pbInput,
            int cbInput,
            ref BCRYPT_AUTHENTICATED_CIPHER_MODE_INFO pPaddingInfo,
            byte[] pbIV,
            int cbIV,
            byte[] pbOutput,
            int cbOutput,
            out int pcbResult,
            uint dwFlags);

        [DllImport("bcrypt.dll")]
        private static extern uint BCryptDecrypt(
            IntPtr hKey,
            byte[] pbInput,
            int cbInput,
            ref BCRYPT_AUTHENTICATED_CIPHER_MODE_INFO pPaddingInfo,
            byte[] pbIV,
            int cbIV,
            byte[] pbOutput,
            int cbOutput,
            out int pcbResult,
            uint dwFlags);

        [DllImport("bcrypt.dll")]
        private static extern uint BCryptDestroyKey(IntPtr hKey);

        [DllImport("bcrypt.dll")]
        private static extern uint BCryptCloseAlgorithmProvider(IntPtr hAlgorithm, uint dwFlags);

        public static bool Initialize(byte[] publicKeyDER)
        {
            // All static fields are assigned atomically at the end to prevent
            // partial initialization state where callers assume encryption works.
            IntPtr hAlg = IntPtr.Zero;
            IntPtr hKey = IntPtr.Zero;
            try
            {
                var rsa = new RSACryptoServiceProvider();
                RSAParameters rsaParams = ParseDERPublicKey(publicKeyDER);
                rsa.ImportParameters(rsaParams);

                byte[] aesKey;
                using (var rng = new RNGCryptoServiceProvider())
                {
                    aesKey = new byte[AES_KEY_SIZE];
                    rng.GetBytes(aesKey);
                }

                uint status = BCryptOpenAlgorithmProvider(out hAlg, BCRYPT_AES_ALGORITHM, null, 0);
                if (status != ERROR_SUCCESS) return false;

                status = BCryptSetProperty(hAlg, BCRYPT_CHAINING_MODE,
                    BCRYPT_CHAIN_MODE_GCM,
                    (BCRYPT_CHAIN_MODE_GCM.Length + 1) * 2, 0);
                if (status != ERROR_SUCCESS) return false;

                status = BCryptGenerateSymmetricKey(hAlg, out hKey, IntPtr.Zero, 0,
                    aesKey, aesKey.Length, 0);
                if (status != ERROR_SUCCESS) return false;

                _rsa = rsa;
                _aesKey = aesKey;
                _hAesAlg = hAlg;
                _hAesKey = hKey;
                hAlg = IntPtr.Zero;
                hKey = IntPtr.Zero;

                return true;
            }
            catch (Exception ex)
            {
                Logger.Warning($"Encryption initialization failed: {ex.Message}");
                return false;
            }
            finally
            {
                if (hKey != IntPtr.Zero) BCryptDestroyKey(hKey);
                if (hAlg != IntPtr.Zero) BCryptCloseAlgorithmProvider(hAlg, 0);
            }
        }

        public static byte[] EncryptRSA(byte[] data)
        {
            try
            {
                int keyBytes = _rsa.KeySize / 8;
                int maxChunk = keyBytes - RSA_PKCS1_PADDING_OVERHEAD;

                if (data.Length <= maxChunk)
                    return _rsa.Encrypt(data, false);

                int numBlocks = (data.Length + maxChunk - 1) / maxChunk;
                byte[] result = new byte[numBlocks * keyBytes];
                int offset = 0;

                for (int i = 0; i < data.Length; i += maxChunk)
                {
                    int chunkLen = Math.Min(maxChunk, data.Length - i);
                    byte[] chunk = new byte[chunkLen];
                    Array.Copy(data, i, chunk, 0, chunkLen);
                    byte[] encrypted = _rsa.Encrypt(chunk, false);
                    Array.Copy(encrypted, 0, result, offset, encrypted.Length);
                    offset += encrypted.Length;
                }

                return result;
            }
            catch (Exception ex)
            {
                Logger.Warning($"RSA encryption failed: {ex.Message}");
                return null;
            }
        }

        public static byte[] EncryptAesGcm(byte[] data, byte[] iv)
        {
            try
            {
                byte[] tag = new byte[GCM_TAG_SIZE];
                var authInfo = BCRYPT_AUTHENTICATED_CIPHER_MODE_INFO.Create();

                GCHandle nonceHandle = GCHandle.Alloc(iv, GCHandleType.Pinned);
                GCHandle tagHandle = GCHandle.Alloc(tag, GCHandleType.Pinned);
                try
                {
                    authInfo.pbNonce = nonceHandle.AddrOfPinnedObject();
                    authInfo.cbNonce = (uint)iv.Length;
                    authInfo.pbTag = tagHandle.AddrOfPinnedObject();
                    authInfo.cbTag = (uint)GCM_TAG_SIZE;

                    byte[] ivBuf = new byte[AES_BLOCK_SIZE];
                    Array.Copy(iv, 0, ivBuf, 0, iv.Length);

                    int ciphertextSize;
                    uint status = BCryptEncrypt(_hAesKey, data, data.Length, ref authInfo,
                        ivBuf, AES_BLOCK_SIZE, null, 0, out ciphertextSize, 0);
                    if (status != ERROR_SUCCESS) return null;

                    byte[] ciphertext = new byte[ciphertextSize];

                    authInfo = BCRYPT_AUTHENTICATED_CIPHER_MODE_INFO.Create();
                    authInfo.pbNonce = nonceHandle.AddrOfPinnedObject();
                    authInfo.cbNonce = (uint)iv.Length;
                    authInfo.pbTag = tagHandle.AddrOfPinnedObject();
                    authInfo.cbTag = (uint)GCM_TAG_SIZE;

                    ivBuf = new byte[AES_BLOCK_SIZE];
                    Array.Copy(iv, 0, ivBuf, 0, iv.Length);

                    status = BCryptEncrypt(_hAesKey, data, data.Length, ref authInfo,
                        ivBuf, AES_BLOCK_SIZE, ciphertext, ciphertext.Length, out ciphertextSize, 0);
                    if (status != ERROR_SUCCESS) return null;

                    byte[] result = new byte[ciphertextSize + GCM_TAG_SIZE];
                    Array.Copy(ciphertext, 0, result, 0, ciphertextSize);
                    Array.Copy(tag, 0, result, ciphertextSize, GCM_TAG_SIZE);

                    return result;
                }
                finally
                {
                    nonceHandle.Free();
                    tagHandle.Free();
                }
            }
            catch (Exception ex)
            {
                Logger.Warning($"AES-GCM encryption failed: {ex.Message}");
                return null;
            }
        }

        public static byte[] DecryptAesGcm(byte[] data, byte[] iv)
        {
            try
            {
                if (data.Length < GCM_TAG_SIZE) return null;

                int ciphertextLen = data.Length - GCM_TAG_SIZE;
                byte[] ciphertext = new byte[ciphertextLen];
                byte[] tag = new byte[GCM_TAG_SIZE];
                Array.Copy(data, 0, ciphertext, 0, ciphertextLen);
                Array.Copy(data, ciphertextLen, tag, 0, GCM_TAG_SIZE);

                var authInfo = BCRYPT_AUTHENTICATED_CIPHER_MODE_INFO.Create();

                GCHandle nonceHandle = GCHandle.Alloc(iv, GCHandleType.Pinned);
                GCHandle tagHandle = GCHandle.Alloc(tag, GCHandleType.Pinned);
                try
                {
                    authInfo.pbNonce = nonceHandle.AddrOfPinnedObject();
                    authInfo.cbNonce = (uint)iv.Length;
                    authInfo.pbTag = tagHandle.AddrOfPinnedObject();
                    authInfo.cbTag = (uint)GCM_TAG_SIZE;

                    byte[] ivBuf = new byte[AES_BLOCK_SIZE];
                    Array.Copy(iv, 0, ivBuf, 0, iv.Length);

                    byte[] plaintext = new byte[ciphertextLen];
                    int plaintextSize;

                    uint status = BCryptDecrypt(_hAesKey, ciphertext, ciphertextLen, ref authInfo,
                        ivBuf, AES_BLOCK_SIZE, plaintext, plaintext.Length, out plaintextSize, 0);
                    if (status != ERROR_SUCCESS)
                    {
                        return null;
                    }

                    if (plaintextSize != ciphertextLen)
                    {
                        byte[] trimmed = new byte[plaintextSize];
                        Array.Copy(plaintext, trimmed, plaintextSize);
                        return trimmed;
                    }

                    return plaintext;
                }
                finally
                {
                    nonceHandle.Free();
                    tagHandle.Free();
                }
            }
            catch (Exception ex)
            {
                Logger.Warning($"AES-GCM decryption failed: {ex.Message}");
                return null;
            }
        }

        public static byte[] GenerateIV()
        {
            byte[] iv = new byte[GCM_IV_SIZE];
            using (var rng = new RNGCryptoServiceProvider())
            {
                rng.GetBytes(iv);
            }
            return iv;
        }

        public static byte[] GetAesKey()
        {
            return _aesKey;
        }

        private static RSAParameters ParseDERPublicKey(byte[] der)
        {
            int offset = 0;

            byte tag;
            int length;

            ReadTLV(der, ref offset, out tag, out length);

            int algIdStart = offset;
            ReadTLV(der, ref offset, out tag, out length);
            offset += length;

            ReadTLV(der, ref offset, out tag, out length);
            offset++;

            ReadTLV(der, ref offset, out tag, out length);

            byte[] modulus = ReadDERInteger(der, ref offset);

            byte[] exponent = ReadDERInteger(der, ref offset);

            return new RSAParameters { Modulus = modulus, Exponent = exponent };
        }

        private static void ReadTLV(byte[] data, ref int offset, out byte tag, out int length)
        {
            tag = data[offset++];
            length = data[offset++];
            if ((length & 0x80) != 0)
            {
                int numBytes = length & 0x7F;
                length = 0;
                for (int i = 0; i < numBytes; i++)
                    length = (length << 8) | data[offset++];
            }
        }

        private static byte[] ReadDERInteger(byte[] data, ref int offset)
        {
            byte tag;
            int len;
            ReadTLV(data, ref offset, out tag, out len);

            byte[] value = new byte[len];
            Array.Copy(data, offset, value, 0, len);
            offset += len;

            if (value.Length > 1 && value[0] == 0x00)
            {
                byte[] trimmed = new byte[value.Length - 1];
                Array.Copy(value, 1, trimmed, 0, trimmed.Length);
                return trimmed;
            }
            return value;
        }
    }
}
