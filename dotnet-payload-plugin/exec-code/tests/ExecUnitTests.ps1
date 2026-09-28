param(
    [string]$AgentPath = (Join-Path $PSScriptRoot '..\bin\Release\dotnet-agent.exe')
)

$ErrorActionPreference = 'Stop'

function New-Tlv([byte]$Type, [byte[]]$Body, [bool]$Parent = $false) {
    $header = New-Object byte[] 5
    $header[0] = if ($Parent) { [byte]($Type -bor 0x80) } else { $Type }
    [Array]::Copy([BitConverter]::GetBytes([uint32]$Body.Length), 0, $header, 1, 4)
    return ,([byte[]]($header + $Body))
}

function New-ListenerTlv([object]$Format) {
    [byte[]]$children = New-Tlv 1 ([byte[]]@(1))
    $children += New-Tlv 3 ([byte[]]@(0x55))
    $children += New-Tlv 4 ([Text.Encoding]::ASCII.GetBytes('TESTPIPE'))
    $children += New-Tlv 5 ([byte[]]@())
    if ($null -ne $Format) {
        [byte[]]$execConf = New-Tlv 1 ([byte[]]@([byte]$Format))
        $children += New-Tlv 7 $execConf $true
    }
    return ,(New-Tlv 1 $children $true)
}

$assembly = [Reflection.Assembly]::LoadFrom((Resolve-Path -LiteralPath $AgentPath).Path)
$tlvType = $assembly.GetType('DotNetAgent.TLV', $true)
$listenerType = $assembly.GetType('DotNetAgent.Listener', $true)

function Test-ListenerLoad([string]$Name, [byte[]]$Bytes, [bool]$Expected) {
    $tlv = [Activator]::CreateInstance($tlvType, $true)
    $args = New-Object object[] 2
    $args[0] = $Bytes
    $args[1] = 0
    if (-not $tlvType.GetMethod('Load').Invoke($tlv, $args)) {
        throw 'Test TLV failed to parse'
    }
    $listener = [Activator]::CreateInstance($listenerType, $true)
    $args = New-Object object[] 1
    $args[0] = $tlv
    $actual = [bool]$listenerType.GetMethod('Load').Invoke($listener, $args)
    if ($actual -ne $Expected) {
        throw "${Name}: Listener.Load returned $actual; expected $Expected"
    }
}

Test-ListenerLoad 'legacy shellcode' (New-ListenerTlv $null) $true
Test-ListenerLoad 'shellcode exec unit' (New-ListenerTlv 0) $true
Test-ListenerLoad '.NET executable' (New-ListenerTlv 1) $false
Test-ListenerLoad '.NET library' (New-ListenerTlv 2) $false
Test-ListenerLoad 'native library' (New-ListenerTlv 3) $false
$malformed = New-Tlv 1 ([byte[]]((New-Tlv 1 ([byte[]]@(1))) + (New-Tlv 3 ([byte[]]@(0x55))) + (New-Tlv 4 ([Text.Encoding]::ASCII.GetBytes('TESTPIPE'))) + (New-Tlv 7 ([byte[]]@()) $true))) $true
Test-ListenerLoad 'missing exec-unit format' $malformed $false

$metadataType = $assembly.GetType('DotNetAgent.Metadata', $true)
[byte[]]$metadataBytes = $metadataType.GetMethod('GetBuffer').Invoke($null, $null)
$metadataTlv = [Activator]::CreateInstance($tlvType, $true)
$args = New-Object object[] 2
$args[0] = $metadataBytes
$args[1] = 0
if (-not $tlvType.GetMethod('Load').Invoke($metadataTlv, $args)) {
    throw 'Agent metadata TLV failed to parse'
}
$args[0] = [byte]0x44
$args[1] = 0
$capabilitiesTlv = $tlvType.GetMethod('GetChild').Invoke($metadataTlv, $args)
if ($null -eq $capabilitiesTlv) {
    throw 'Agent metadata is missing capabilities child 0x44'
}
[byte[]]$capabilities = $tlvType.GetProperty('Data').GetValue($capabilitiesTlv, $null)
if ($capabilities.Length -ne 9 -or $capabilities[8] -ne 0x01) {
    throw 'Agent must advertise only native shellcode execution in its own process'
}
for ($i = 0; $i -lt 8; $i++) {
    if ($capabilities[$i] -ne 0) { throw "Unexpected capability bit at byte $i" }
}

Write-Host 'Shellcode listener TLV and metadata capability tests passed.'
