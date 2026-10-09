package com.example.tuoni.command;

import com.shelldot.tuoni.plugin.sdk.command.ExecUnit;
import com.shelldot.tuoni.plugin.sdk.command.ExecUnitType;
import com.shelldot.tuoni.plugin.sdk.common.*;
import com.shelldot.tuoni.plugin.sdk.common.exceptions.SerializationException;
import com.shelldot.tuoni.plugin.sdk.payload.PayloadType;
import java.lang.reflect.Proxy;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.nio.charset.StandardCharsets;
import java.util.Arrays;
import java.util.Set;

/** Runs in the Docker Java build against the freshly compiled execution resources.
 * Does not load native code or establish host IPC/lifecycle correctness. */
public final class ExecUnitFormatsCheck {
  private static final byte[] CONFIG = new byte[0];

  public static void main(String[] args) throws Exception {
    for (String name : new String[] {"command"}) {
      for (OperatingSystem os : OperatingSystem.values()) {
        for (Architecture arch : Architecture.values()) {
          Set<ExecUnitType> expected = os == OperatingSystem.WINDOWS
                  && (arch == Architecture.X86 || arch == Architecture.X64)
              ? Set.of(ExecUnitType.SHELLCODE_NATIVE, ExecUnitType.DOTNET_DLL,
                  ExecUnitType.DOTNET_EXE, ExecUnitType.NATIVE_LIB)
              : os == OperatingSystem.LINUX && arch == Architecture.X64
                  ? Set.of(ExecUnitType.NATIVE_LIB) : Set.of();
          require(supported(os, arch).equals(expected), "Supported formats: " + os + "/" + arch);
          for (ExecUnitType type : ExecUnitType.values()) {
            if (!expected.contains(type)) {
              try {
                generate(name, os, arch, type, "TESTPIPE1");
                throw new AssertionError("Accepted unsupported " + os + "/" + arch + "/" + type);
              } catch (SerializationException expectedFailure) {
                // Reject the combination before accessing an unrelated resource.
              }
              continue;
            }
            // Managed formats must allow pipe names longer than the shellcode marker.
            String pipe = type == ExecUnitType.SHELLCODE_NATIVE ? "TESTPIPE1" : "a-long-managed-pipe-name";
            ExecUnit unit = generate(name, os, arch, type, pipe);
            require(unit.type() == type && unit.ipcType() == PluginIpcType.NAMED_PIPE, "Execunit metadata");
            require(unit.code().position() == 0 && unit.code().hasRemaining(), "Code buffer bounds");
            require(unit.configuration().position() == 0, "Configuration position");
            require(Arrays.equals(bytes(unit.configuration()), CONFIG), "Configuration changed by format");
            String resource = switch (type) {
              case DOTNET_DLL -> "/command.dotnet_dll";
              case DOTNET_EXE -> "/command.dotnet_exe";
              case SHELLCODE_NATIVE -> "/command.shellcode";
              case NATIVE_LIB -> os == OperatingSystem.WINDOWS
                  ? (arch == Architecture.X86 ? "/command.native32_dll" : "/command.native64_dll")
                  : "/command-linux.native64_so";
            };
            byte[] original = resource(resource);
            byte[] code = bytes(unit.code());
            if (type == ExecUnitType.SHELLCODE_NATIVE) {
              require(unit.entrypoint() == null, "Shellcode entrypoint");
              require(!Arrays.equals(code, original), "Shellcode was not patched");
              require(contains(code, pipe.getBytes(StandardCharsets.UTF_16LE)), "Patched pipe missing");
              require(!contains(code, "QQQWWWEEE".getBytes(StandardCharsets.UTF_16LE)), "Unpatched pipe remains");
            } else {
              require(Arrays.equals(code, original), "Loader resource was modified: " + resource);
              if (type == ExecUnitType.DOTNET_DLL || type == ExecUnitType.DOTNET_EXE) {
                verifyManagedPe(code, type == ExecUnitType.DOTNET_DLL);
                String entrypoint = type == ExecUnitType.DOTNET_DLL
                    ? new String(resource(resource + "_method"), StandardCharsets.UTF_8).trim() : null;
                require(java.util.Objects.equals(entrypoint, unit.entrypoint()), "DLL entrypoint metadata");
              } else if (os == OperatingSystem.WINDOWS) {
                verifyNativePe(code, arch);
                require("start".equals(unit.entrypoint()), "Windows native entrypoint");
              } else {
                require(code.length > 20 && code[0] == 0x7f && code[1] == 'E'
                    && code[2] == 'L' && code[3] == 'F' && code[4] == 2, "Expected ELF64 library");
                require("run".equals(unit.entrypoint()), "Linux entrypoint");
              }
            }
            // Loading/generation must return independent code/configuration buffers.
            unit.code().put(0, (byte) 0);
            unit.configuration().position(unit.configuration().limit());
            ExecUnit again = generate(name, os, arch, type, pipe);
            require(Arrays.equals(code, bytes(again.code())), "Mutated shared artifact");
            require(again.configuration().position() == 0
                && Arrays.equals(CONFIG, bytes(again.configuration())), "Reused configuration cursor");
          }
        }
      }
    }
    System.out.println("Execution format selection, PE roles, entrypoints and resource bytes verified.");
  }

  private static Set<ExecUnitType> supported(OperatingSystem os, Architecture arch) {
    return TemplateCommand.supportedTypes(metadata(os, arch));
  }

  private static ExecUnit generate(String name, OperatingSystem os, Architecture arch,
      ExecUnitType type, String pipe) throws Exception {
    return new TemplateCommand(1, agent(os, arch), null, null).generateExecUnit(type, pipe);
  }

  private static AgentMetadata metadata(OperatingSystem os, Architecture arch) {
    return AgentMetadata.builder(new java.util.UUID(0L, 1L))
        .os(os)
        .processArch(arch)
        .build();
  }

  private static AgentInfo agent(OperatingSystem os, Architecture arch) {
    return (AgentInfo) Proxy.newProxyInstance(AgentInfo.class.getClassLoader(),
        new Class<?>[] {AgentInfo.class}, (proxy, method, args) -> switch (method.getName()) {
          case "getLatestMetadata" -> metadata(os, arch);
          case "getType" -> AgentType.SHELLCODE_AGENT;
          default -> throw new AssertionError("Unexpected agent call: " + method);
        });
  }

  private static byte[] resource(String path) throws Exception {
    try (var input = ExecUnitFormatsCheck.class.getResourceAsStream(path)) {
      require(input != null, "Missing resource: " + path);
      return input.readAllBytes();
    }
  }

  private static byte[] bytes(ByteBuffer input) {
    byte[] result = new byte[input.remaining()];
    input.asReadOnlyBuffer().get(result);
    return result;
  }

  private static void verifyManagedPe(byte[] bytes, boolean dll) {
    require(bytes.length > 64 && bytes[0] == 'M' && bytes[1] == 'Z', "Expected PE image");
    ByteBuffer pe = ByteBuffer.wrap(bytes).order(ByteOrder.LITTLE_ENDIAN);
    int header = pe.getInt(0x3c);
    require(pe.getInt(header) == 0x4550, "PE signature");
    require(((pe.getShort(header + 22) & 0x2000) != 0) == dll, "PE DLL/EXE role");
    int optional = header + 24;
    int directory = optional + (pe.getShort(optional) == 0x20b ? 112 : 96);
    require(pe.getInt(directory + 14 * 8) != 0, "Missing CLR header");
  }

  private static void verifyNativePe(byte[] bytes, Architecture arch) {
    require(bytes.length > 64 && bytes[0] == 'M' && bytes[1] == 'Z', "Expected native PE image");
    ByteBuffer pe = ByteBuffer.wrap(bytes).order(ByteOrder.LITTLE_ENDIAN);
    int header = pe.getInt(0x3c);
    require(pe.getInt(header) == 0x4550, "Native PE signature");
    int machine = Short.toUnsignedInt(pe.getShort(header + 4));
    require(machine == (arch == Architecture.X86 ? 0x14c : 0x8664), "Native process architecture");
    require((pe.getShort(header + 22) & 0x2000) != 0, "Native PE must be a DLL");
    int optional = header + 24;
    int directories = optional + (arch == Architecture.X86 ? 96 : 112);
    require(pe.getInt(directories + 14 * 8) == 0, "Native DLL must not contain a CLR header");
  }

  private static boolean contains(byte[] bytes, byte[] value) {
    for (int offset = 0; offset <= bytes.length - value.length; offset++) {
      if (Arrays.equals(bytes, offset, offset + value.length, value, 0, value.length)) {
        return true;
      }
    }
    return false;
  }

  private static void require(boolean condition, String message) {
    if (!condition) throw new AssertionError(message);
  }
}
