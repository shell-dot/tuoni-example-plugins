# Command result parsing and presentation

Read this when implementing `parseResult` in `java-plugin/src/main/java/com/example/tuoni/command/TemplateCommand.java`. The buffer contains the result payload after agent IPC handling; do not parse the outer `0x30` frame again. Define the payload contract with every native sender using the [IPC reference](execunit-ipc.md).

The [implemented default](../README.md#default-behavior) sends exact UTF-8 `DONE` (`44 4f 4e 45`), with no newline or terminator. `TemplateCommand.parseResult` strictly decodes each complete nonempty payload using a read-only buffer, calls `appendTextResult("output", text)`, then `commit()`. Empty notifications return without editing results. Keep that simple path for complete text; add stateful reassembly only when the requested output needs split characters or records.

The native sender hooks are managed Windows `Execute` in `exec-code/win/Program.cs`, the `runCommand` callback in `exec-code/win-native/command/Main.cpp`, and Linux `execute` in `exec-code/linux/command/Main.cpp`. Update all three to preserve one payload contract; add C# sources to the `.csproj`, Windows C++ sources to `exec-code/win-native/build_windows.sh`, and Linux C++ sources to `exec-code/linux/build_linux.sh`. Preserve checked sends and the existing completion/cleanup owners.

## Payload formats

Decode the format agreed with each native sender: raw UTF-8 for simple text, JSON when structured data and parser dependencies warrant it, or an explicit binary layout for fields/files. The SDK delivers inner payload bytes after host framing; Java requires no host-envelope codec. Use standard Java text/byte APIs for raw payloads and declare/bundle any JSON parser in the plugin build.

Validate field types, lengths, size limits and malformed text before publishing. For chunked records, retain incomplete bytes until a whole record is available, then parse it; reject an incomplete record at final notification. For file results, pass the actual file bytes to the result editor. Native helpers own error/completion messages separately from successful payloads. Apply the [command completion gate](command-completion.md): even an empty result needs terminal success, and failed encoding must reach terminal failure. Error text and `isFinalResult` are not terminal success/failure reports; test the host's final command state as well as displayed output.

## State ownership and multipart results

The [existing result patterns](existing-plugins.md#results-and-state) show a decoder producing typed chunks, a merger enforcing stream rules, and a renderer producing result entries. Use that separation when a command needs multipart data; keep a one-value command simple.

In this template, mutable parsing state belongs to the individual `TemplateCommand`. In a `SimpleStateless*CommandTemplate` pattern, the template instance serves many executions: reconstruct state from that command's `previousResult` or use its command object. Where state must survive reconstruction, validate its agent/command/request identity and version before merging. Publish internal state with `editor.editMetadata(name, metadata -> metadata.withVisibility(ResultVisibility.PLUGIN_ONLY))` where supported; preserve stable public result names.

For an established multipart contract, enforce its sequence, duplicate, terminal, partial/truncated, and aggregate-size rules. `isFinalResult` means the stream has ended; it does not turn an absent terminal record, partial result, or native failure into success. Retain valid earlier data according to the contract. Validate a complete chunk and candidate merged state before committing presentation changes.

## Result editor calls

The SDK 0.15.0 `CommandResultEditor` provides these relevant signatures. Keep stable result entry names unless the user requests a change.

| Output | Calls | Behavior |
| --- | --- | --- |
| Text | `setTextResult(String name, String value)` / `appendTextResult(String name, String value)` | Replace a complete value / add only newly decoded text. |
| Binary result | `setByteArrayResult(String name, byte[] value)` or `(String, ByteBuffer)` | Store uninterpreted bytes as a result value. |
| Complete downloadable file | `setFile(String name, byte[] value)`, `(String, ByteBuffer)`, or `(String, InputStream)` | Store the requested file bytes. |
| File continuation | `appendToFile(String name, ByteBuffer value)` or `(String, InputStream)` | Append new file data; there is no `byte[]` overload. Use `ByteBuffer.wrap(bytes)` when needed. |
| Publish edits | `commit()` | Commit each completed editor update. |

Use `buffer.slice()` or a duplicate to consume only the supplied `position..limit` without relying on `array()`: SDK buffers can be direct, read-only, or slices with nonzero offsets. For structured output, validate a complete record before publishing its fields. Match signedness, byte order, and string encoding to the native contract.

## Strict UTF-8, one complete value

`StandardCharsets.UTF_8.decode` replaces malformed input. To implement the requirement to reject malformed text, use an explicit decoder:

```java
private static String decodeText(ByteBuffer payload) throws SerializationException {
  try {
    return StandardCharsets.UTF_8.newDecoder()
        .onMalformedInput(CodingErrorAction.REPORT)
        .onUnmappableCharacter(CodingErrorAction.REPORT)
        .decode(payload.slice()).toString();
  } catch (CharacterCodingException error) {
    throw new SerializationException("Malformed UTF-8 result", error);
  }
}
```

Import `java.nio.ByteBuffer`, the used types from `java.nio.charset`, and SDK `common.exceptions.SerializationException`. For a one-value contract, use `editor.setTextResult("message", decodeText(buffer)); editor.commit();`. Preserve an existing value on a separate empty final notification; only treat an empty buffer as a new empty value when that is what the result contract means. If multiple values/chunks are expected, use append/reassembly semantics instead of replacing earlier output.

## Streaming text with incomplete UTF-8

For UTF-8 text split across result buffers, keep one decoder per command instance, not a static decoder shared by commands. The following helper retains at most three incomplete bytes between calls. Its 1 MiB per-call bound is an example: choose and document a bound compatible with native output and agent delivery limits. This helper consumes raw text payload bytes, not pipe headers. If the command uses structured records instead, reassemble and decode those records before passing their text fields to it.

```java
import com.shelldot.tuoni.plugin.sdk.common.exceptions.SerializationException;
import java.nio.ByteBuffer;
import java.nio.CharBuffer;
import java.nio.charset.CharacterCodingException;
import java.nio.charset.CharsetDecoder;
import java.nio.charset.CoderResult;
import java.nio.charset.CodingErrorAction;
import java.nio.charset.StandardCharsets;

final class Utf8Chunks {
  private static final int MAX_CHUNK_BYTES = 1024 * 1024;
  private final CharsetDecoder decoder = StandardCharsets.UTF_8.newDecoder()
      .onMalformedInput(CodingErrorAction.REPORT)
      .onUnmappableCharacter(CodingErrorAction.REPORT);
  private byte[] pending = new byte[0];
  private boolean finished;

  String accept(ByteBuffer source, boolean isFinal) throws SerializationException {
    if (finished) {
      throw new SerializationException("Result stream is already finished");
    }
    if (source.remaining() > MAX_CHUNK_BYTES) {
      throw new SerializationException("Result chunk exceeds the agreed limit");
    }
    ByteBuffer input = ByteBuffer.allocate(pending.length + source.remaining());
    input.put(pending).put(source.slice()).flip();
    // UTF-8 produces at most one UTF-16 code unit per input byte.
    CharBuffer text = CharBuffer.allocate(input.remaining());
    try {
      CoderResult decoded = decoder.decode(input, text, isFinal);
      if (decoded.isError()) decoded.throwException();
      if (decoded.isOverflow() || input.remaining() > 3) {
        throw new SerializationException("Unexpected UTF-8 decoder state");
      }
      pending = new byte[input.remaining()];
      input.get(pending);
      if (isFinal) {
        CoderResult flushed = decoder.flush(text);
        if (flushed.isError()) flushed.throwException();
        if (flushed.isOverflow()) {
          throw new SerializationException("Unexpected UTF-8 flush state");
        }
        finished = true;
        pending = new byte[0];
      }
      text.flip();
      return text.toString();
    } catch (CharacterCodingException error) {
      discard();
      throw new SerializationException("Malformed or truncated UTF-8 result", error);
    }
  }

  void discard() {
    pending = new byte[0];
    decoder.reset();
    finished = true;
  }
}
```

Place the helper in the same Java package (or adapt an existing parser), retain it as a command field, then for each raw text buffer call `String text = decoder.accept(buffer, isFinalResult);`, append only nonempty `text`, and `editor.commit()`. For structured records with embedded text, pass only the extracted text and mark its final chunk after all final records are validated. An empty final notification still reaches `accept` to reject a truncated trailing character; it does not replace accumulated output. On parser failure or command disposal call `discard()`; do not discard during a status callback if final parsing is still pending. Serialize access if the host can invoke parsing and disposal concurrently.

For structured streams, keep at most the agreed maximum incomplete record, process complete records once, and retain only the suffix. On the final call reject a remaining incomplete header/body. For file streams, append the actual content bytes under the agreed file name; exclude any application metadata and do not decode file bytes as text. Configure ongoing/block-relay options before native sends, as described in the IPC reference.

## Focused checks

Use the [two-level payload verification](payload-verification.md) to prove each native encoder agrees with the actual Java parser and the real transport delivers the expected inner bytes. Retest startup configuration when output changes affect shared helpers or resources; the final integrated smoke check covers both directions.

Send fixtures from each native encoder into the Java parser. Include direct/read-only/sliced buffers, empty data, two chunks splitting a multibyte character or record, malformed text/lengths, an empty final notification, and a truncated final record where applicable. Assert accumulated text/file bytes and entry names, not only that parsing returns. For the UTF-8 helper above, the chunks `41 E2`, `82`, `AC 42`, then an empty final chunk must produce `A`, empty text, `\u20acB`, then empty text; `E2` followed by a final empty chunk must fail.
