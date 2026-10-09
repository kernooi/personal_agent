param(
    [string]$Profile = "$env:LOCALAPPDATA\Jarvis\profiles\laptop.toml",
    [string]$Report = "$env:LOCALAPPDATA\Jarvis\offline-check.json",
    [ValidateRange(0, 300)]
    [int]$WaitForDisconnectSeconds = 0
)

# Development-time check only. Reads network state; never disables interfaces,
# modifies routes/firewalls, installs software, or provides a JARVIS shell tool.
$ErrorActionPreference = 'Stop'
$jarvisPython = Join-Path $PSScriptRoot '..\.venv\Scripts\python.exe'

function Get-JarvisNetworkState {
    $jarvisAdapters = @(Get-NetAdapter -IncludeHidden -ErrorAction Stop)
    $jarvisRoutes = @(Get-NetRoute -PolicyStore ActiveStore -ErrorAction Stop)
    $jarvisInactiveStatuses = @('Disconnected', 'Disabled', 'Not Present', 'NotPresent', 'LowerLayerDown')
    $jarvisInactiveIndices = @($jarvisAdapters | Where-Object {
        $_.Status -in $jarvisInactiveStatuses
    } | Select-Object -ExpandProperty ifIndex)
    $jarvisDefaultRoutes = @($jarvisRoutes | Where-Object {
        $_.DestinationPrefix -in @('0.0.0.0/0', '::/0')
    })
    return [ordered]@{
        captured_at_utc = [DateTime]::UtcNow.ToString('o')
        physical_adapters_up = @($jarvisAdapters | Where-Object {
            $_.HardwareInterface -and $_.Status -eq 'Up'
        }).Count
        any_adapters_up = @($jarvisAdapters | Where-Object { $_.Status -eq 'Up' }).Count
        physical_adapters_unknown = @($jarvisAdapters | Where-Object {
            $_.HardwareInterface -and $_.Status -ne 'Up' -and
            $_.Status -notin $jarvisInactiveStatuses
        }).Count
        configured_default_routes = $jarvisDefaultRoutes.Count
        # Disconnected-interface routes may remain configured. Unknown peers count
        # as active; only positively inactive interfaces can be excluded.
        default_routes = @($jarvisDefaultRoutes | Where-Object {
            $_.InterfaceIndex -notin $jarvisInactiveIndices
        }).Count
    }
}

function Test-JarvisDisconnected($State) {
    return $State.physical_adapters_up -eq 0 -and
        $State.physical_adapters_unknown -eq 0 -and $State.default_routes -eq 0
}

function Write-JarvisOfflineReport($Value) {
    $jarvisReportPath = [IO.Path]::GetFullPath($Report)
    [IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName($jarvisReportPath)) | Out-Null
    $jarvisJson = $Value | ConvertTo-Json -Depth 12
    [IO.File]::WriteAllText($jarvisReportPath, $jarvisJson + [Environment]::NewLine,
        [Text.UTF8Encoding]::new($false))
    Write-Output $jarvisJson
}

$jarvisBefore = Get-JarvisNetworkState
$jarvisWaitDeadline = [DateTime]::UtcNow.AddSeconds($WaitForDisconnectSeconds)
if ($WaitForDisconnectSeconds -gt 0 -and -not (Test-JarvisDisconnected $jarvisBefore)) {
    [Console]::Error.WriteLine("Waiting up to $WaitForDisconnectSeconds seconds for manual network disconnection.")
    while (-not (Test-JarvisDisconnected $jarvisBefore) -and
            [DateTime]::UtcNow -lt $jarvisWaitDeadline) {
        Start-Sleep -Milliseconds 1000
        $jarvisBefore = Get-JarvisNetworkState
    }
}
if (-not (Test-JarvisDisconnected $jarvisBefore)) {
    Write-JarvisOfflineReport ([ordered]@{
        status = 'blocked'
        check_version = 'offline-check-v2'
        reason = 'External network adapter or default route remains active; disconnect manually.'
        network_before = $jarvisBefore
        model_inference_ran = $false
        offline_network_isolation_tested = $false
    })
    exit 2
}

$jarvisSmokeJson = @'
import json
import sys
import tempfile
from dataclasses import asdict
from pathlib import Path
from jarvis.bootstrap import build, load_profile
from jarvis.domain import State, UserRequest
from jarvis.models import OllamaProfile
profile = load_profile(Path(sys.argv[1]), allow_ollama=True)
if not isinstance(profile, OllamaProfile):
    raise ValueError('An explicit local Ollama profile is required')
with tempfile.TemporaryDirectory(prefix='jarvis-offline-smoke-') as directory:
    broker = build(Path(directory) / 'journal.sqlite', profile)
    try:
        before = len(broker.desktop.running)
        result = broker.converse(UserRequest('offline-editor', 'demo-session',
                                            'Open my registered text editor.'))
        passed = (result.state == State.SUCCEEDED and before == 0
                  and len(broker.desktop.running) == 1
                  and broker.desktop.execution_calls == broker.desktop.effect_count == 1
                  and broker.desktop.observation_calls == 1)
        print(json.dumps({'passed': passed, 'result': asdict(result),
                          'model_metadata': broker.provider.metadata,
                          'prompt_version': profile.prompt_version,
                          'execution_mode': profile.execution_mode,
                          'fake_running_before': before,
                          'fake_running_after': len(broker.desktop.running),
                          'execution_calls': broker.desktop.execution_calls,
                          'observation_calls': broker.desktop.observation_calls,
                          'error': broker.last_error}))
    finally:
        broker.store.close()
        broker.provider.close()
'@ | & $jarvisPython - $Profile
if ($LASTEXITCODE -ne 0) {
    throw 'JARVIS inference check failed; no successful offline evidence was recorded.'
}
$jarvisSmoke = $jarvisSmokeJson | ConvertFrom-Json
$jarvisAfter = Get-JarvisNetworkState
$jarvisPassed = $jarvisSmoke.passed -and (Test-JarvisDisconnected $jarvisAfter)
Write-JarvisOfflineReport ([ordered]@{
    status = $(if ($jarvisPassed) { 'passed' } else { 'failed' })
    check_version = 'offline-check-v2'
    evidence_level = 'Physical-adapter/default-route snapshots before and after actual loopback inference.'
    limitation = 'Snapshots do not continuously attest network state or prove absence of a hidden tunnel.'
    network_before = $jarvisBefore
    network_after = $jarvisAfter
    model_inference_ran = $true
    offline_network_isolation_tested = [bool]$jarvisPassed
    simulated_smoke = $jarvisSmoke
})
if (-not $jarvisPassed) { exit 1 }
