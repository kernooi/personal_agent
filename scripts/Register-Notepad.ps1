param([string]$Output = "$env:LOCALAPPDATA\Jarvis\notepad-registration.json")
# Development-time observational registration. No launch, settings or session reads.
$ErrorActionPreference = 'Stop'
$jarvisPackage = Get-AppxPackage Microsoft.WindowsNotepad
if (@($jarvisPackage).Count -ne 1 -or $jarvisPackage.Status -ne 'Ok' -or
    $jarvisPackage.SignatureKind -ne 'Store' -or
    $jarvisPackage.Publisher -ne 'CN=Microsoft Corporation, O=Microsoft Corporation, L=Redmond, S=Washington, C=US') {
    throw 'A healthy, Microsoft-signed packaged Notepad installation is required for this adapter.'
}
$jarvisLauncher = Join-Path $env:WINDIR 'System32\notepad.exe'
$jarvisExecutable = Join-Path $jarvisPackage.InstallLocation 'Notepad\Notepad.exe'
foreach ($jarvisBinary in @($jarvisLauncher, $jarvisExecutable)) {
    $jarvisSignature = Get-AuthenticodeSignature -LiteralPath $jarvisBinary
    if ($jarvisSignature.Status -ne 'Valid' -or
        $jarvisSignature.SignerCertificate.Subject -notmatch '^CN=Microsoft (Windows|Corporation),') {
        throw 'Notepad binary identity is not verified Microsoft code.'
    }
}
$jarvisRegistration = [ordered]@{
    version = 'notepad-registration-v1'
    app_id = 'notepad'
    launcher = [IO.Path]::GetFullPath($jarvisLauncher)
    launcher_sha256 = (Get-FileHash -LiteralPath $jarvisLauncher -Algorithm SHA256).Hash.ToLower()
    executable = [IO.Path]::GetFullPath($jarvisExecutable)
    executable_sha256 = (Get-FileHash -LiteralPath $jarvisExecutable -Algorithm SHA256).Hash.ToLower()
    package_full_name = $jarvisPackage.PackageFullName
    notepad_version = $jarvisPackage.Version.ToString()
    microsoft_signature_verified = $true
}
$jarvisOutputPath = [IO.Path]::GetFullPath($Output)
if (Test-Path -LiteralPath $jarvisOutputPath) {
    throw 'Registration already exists. Inspect it; choose a new output path for deliberate re-registration.'
}
[IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName($jarvisOutputPath)) | Out-Null
[IO.File]::WriteAllText($jarvisOutputPath, ($jarvisRegistration | ConvertTo-Json) + [Environment]::NewLine,
    [Text.UTF8Encoding]::new($false))
Write-Output "Verified registration written to $jarvisOutputPath. No Notepad windows were launched."
