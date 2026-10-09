# Choosing and recording exec-unit support

Use this guide when a developer limits operating systems, architectures, or
exec-unit formats. Read the [exec-unit overview](execunit-overview.md) for the
existing source families. This guide explains scope and support claims; its
examples do not change the template's current support.

## Interpret the requested limit

Explicit developer limits take precedence over a skill's default of covering
every existing exec-unit. Carry the same limits through creation, focused skills,
reviews, and final reporting. Without a limit, preserve existing coverage.

First distinguish what the developer is limiting:

| Request | Meaning |
| --- | --- |
| "This plugin should support only Linux." | A support requirement: other operating systems are outside the desired supported set. Record any difference from the plugin's current declarations. |
| "Make this change in managed Windows only." | A limit on this task. Other implementations retain their existing status; the new behavior must not be claimed for them. |
| "Test Linux only." | A limit on verification. It does not withdraw Windows support or establish Windows correctness. |
| "Start with Linux." | An ordering or milestone constraint unless context also limits final support. Do not describe the rest of an already requested task as excluded or complete. |

Infer intent from the full request and established project decisions. Ask a
focused question only when unresolved ambiguity would change the supported set
or cause incompatible work. An explicit "only support" request already supplies
the scope decision; it does not need confirmation merely because the template
contains more implementations.

## Keep the dimensions separate

Describe each combination as **OS + process architecture + exec-unit format**,
and identify its source family separately.

| Dimension | What it tells you |
| --- | --- |
| Operating system | Which existing OS implementations are included, such as Windows or Linux. |
| Process architecture | Which architecture is intended, such as x86 or x64. The workstation's OS architecture alone does not settle this. |
| Exec-unit format | Which representation is intended, such as `DOTNET_DLL` or `NATIVE_LIB`. |
| Source family | Which existing implementation supplies that representation: managed Windows, native Windows, or Linux. One family can supply multiple formats. |

For a request to narrow existing support, retain combinations that satisfy
**all** stated limits. Leave unspecified dimensions at their established values.
Do not invent a cross-product of OSs and formats that the source never supported.
A requested combination absent from the inventory is a requirement or gap, not
proof that support exists.

If no existing combination meets the stated limits, report the mismatch. Do not
silently substitute another OS or format or describe the request as fulfilled.

Examples using the fresh template's inventory:

| Developer wording | Interpretation |
| --- | --- |
| "Windows only" | Windows remains selected with its existing architectures and formats; this does not mean native DLLs only. |
| "Linux only" | The existing Linux x64 native-library combination; this does not add Linux x86, ARM, or managed formats. |
| "Only `DOTNET_DLL`" | The managed Windows DLL format on its existing architectures; it does not include native Windows DLLs. |
| "Only `NATIVE_LIB`" | The existing native-library combinations on Windows and Linux; the format alone does not choose an OS. |
| "No shellcode; retain everything else" | Exclude only `SHELLCODE_NATIVE` from the desired set. The shared C# family still supplies the managed EXE/DLL formats. |
| "x64 only" | Existing x64 combinations across OSs and formats; it does not choose Windows or a particular format. |
| "Windows x64 DLL only" | The OS and architecture are clear, but DLL may mean managed or native. Resolve that distinction from context or ask before excluding either. |

## Record desired support separately from evidence

Keep a concise support table in the plugin's [project context](../AGENTS.md),
with one row per combination when its status differs. Useful columns are:

| Column | What to record |
| --- | --- |
| OS / architecture / format | The exact combination, using the project's names. |
| Requested scope | Included, excluded by a support requirement, or outside this task only. |
| Source family and current behavior | The implementation that actually exists and whether this task changed it. |
| Advertised support | What the current plugin declares, independently of what was requested. |
| Artifact evidence | Whether a current artifact exists and which build established that fact; source presence alone is insufficient. |
| Verification | Checks actually run and their outcomes, or the exact unverified portion. |

For example, a request for only Windows x64 `DOTNET_DLL` can be recorded before
any changes as "selected; source exists; declarations still need reconciliation;
build/runtime unverified." Remaining combinations are outside the desired support
set, but their files and current declarations may still exist. This describes
the gap honestly; it does not claim the requested support restriction is already
implemented.

Do not use "unsupported" as a synonym for "untested," "unchanged," or "not part of
this task." Do not silently withdraw coverage because a toolchain or test host is
unavailable. Conversely, a retained source directory does not by itself justify a
public support claim.

## Apply the scope consistently

- Interpret coverage phrases such as "all exec-units," "every native decoder,"
  and "both generation paths" within the explicit requested scope. Inventory can
  still describe every existing family; inventory is not an instruction to expand
  the task.
- Follow only the platform/format-specific branches that apply. A smaller support
  set does not waive correctness requirements for the included combinations.
- Distinguish support restriction from source deletion. A request for a smaller
  supported set does not require deleting other implementations or shared files.
- Shared source can affect several formats. A format-specific task does not prove
  that sibling formats are unaffected; record any wider impact and uncertainty.
- A task-only limit does not make a shared contract change compatible with
  untouched implementations. Record conflicts instead of claiming unchanged
  support is verified.
- Compare the requested set, declared support, documented behavior, and artifact
  evidence when assessing completion. A README edit or filtered inventory alone
  does not establish an implemented support restriction.
- Scope limits do not automatically waive existing build or verification
  requirements. Report unavailable checks separately from intentional exclusions;
  never label a partial check a complete build.
- Finish by stating the selected combinations, intentional exclusions, retained
  support outside the task, actual checks, and remaining discrepancies.

Use [context maintenance](project-context.md) to keep those facts current. In a
generated plugin, use that plugin's local inventory and names instead of assuming
the source template's full matrix still applies.
