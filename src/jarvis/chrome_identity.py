"""Installed stable Google Chrome discovery; no PATH lookup or personal profile reads."""

import hashlib
import json
import os
import subprocess
from pathlib import Path

from pydantic import Field

from jarvis.media_data import MediaError
from jarvis.models import StrictRecord


class ChromeIdentity(StrictRecord):
    executable: str = Field(min_length=1, max_length=512)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    version: str = Field(pattern=r"^\d+\.\d+\.\d+\.\d+$")
    product: str = Field(max_length=40)
    signer: str = Field(max_length=1000)


def private_browser_root():
    if os.name != "nt" or not os.environ.get("LOCALAPPDATA"):
        raise MediaError("WINDOWS_CHROME_REQUIRED")
    return Path(os.environ["LOCALAPPDATA"]) / "Jarvis/browser/chrome"


def no_reparse(path):
    for part in (path, *path.parents):
        if part.exists() and (part.is_symlink() or part.is_junction()):
            raise MediaError("REPARSE_PATH_REJECTED")


def validate_profile(path, repository):
    expected = private_browser_root().absolute()
    path = Path(path).absolute()
    no_reparse(path)
    if path != expected or path.is_relative_to(Path(repository).resolve()):
        raise MediaError("DEDICATED_PRIVATE_PROFILE_REQUIRED")
    return path


def discover_chrome():
    if os.name != "nt":
        raise MediaError("WINDOWS_CHROME_REQUIRED")
    candidates = [
        Path(os.environ[name]) / "Google/Chrome/Application/chrome.exe"
        for name in ("ProgramFiles", "ProgramFiles(x86)", "LOCALAPPDATA")
        if os.environ.get(name)
    ]
    shell = Path(os.environ["SystemRoot"]) / "System32/WindowsPowerShell/v1.0/powershell.exe"
    for path in candidates:
        if not path.is_file():
            continue
        no_reparse(path)
        quoted = str(path).replace("'", "''")
        # Constant trusted script; input comes only from fixed installation locations.
        script = (
            f"$p='{quoted}'; $s=Get-AuthenticodeSignature -LiteralPath $p; "
            "$v=(Get-Item -LiteralPath $p).VersionInfo; "
            "@{valid=($s.Status -eq 'Valid'); signer=$s.SignerCertificate.Subject; "
            "version=$v.ProductVersion; product=$v.ProductName} | ConvertTo-Json -Compress"
        )
        response = subprocess.run(
            [str(shell), "-NoProfile", "-NonInteractive", "-Command", script],
            capture_output=True,
            timeout=15,
            check=True,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        data = json.loads(response.stdout.decode("utf-8-sig"))
        if (
            not data["valid"]
            or "O=Google LLC," not in data["signer"]
            or data["product"] != "Google Chrome"
        ):
            raise MediaError("UNTRUSTED_CHROME_IDENTITY")
        return ChromeIdentity(
            executable=str(path),
            sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
            version=data["version"],
            product=data["product"],
            signer=data["signer"],
        )
    raise MediaError("STABLE_GOOGLE_CHROME_NOT_FOUND")


def create_registration(path, repository):
    identity = discover_chrome()
    root = validate_profile(private_browser_root(), repository)
    registration = Path(path)
    no_reparse(registration)
    if registration.resolve().is_relative_to(Path(repository).resolve()):
        raise MediaError("PRIVATE_REGISTRATION_REQUIRED")
    if root.exists() and any(root.iterdir()):
        raise MediaError("EXISTING_PROFILE_PRESERVED")
    if registration.exists():
        raise MediaError("EXISTING_REGISTRATION_PRESERVED")
    root.mkdir(parents=True, exist_ok=True)
    registration.parent.mkdir(parents=True, exist_ok=True)
    with registration.open("x", encoding="utf-8") as stream:
        json.dump(identity.model_dump(), stream, indent=2)
    return identity


def load_registration(path):
    from jarvis.media_data import parse_record

    path = Path(path)
    no_reparse(path)
    if path.stat().st_size > 32768:
        raise MediaError("REGISTRATION_SIZE_REJECTED")
    pinned = parse_record(path.read_bytes(), ChromeIdentity)
    live = discover_chrome()
    if live != pinned:
        raise MediaError("CHROME_UPDATED_OR_IDENTITY_CHANGED_REREGISTER_MANUALLY")
    return live
