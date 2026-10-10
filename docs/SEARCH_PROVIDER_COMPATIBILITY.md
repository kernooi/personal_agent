# SearXNG provider compatibility and Windows setup

Reviewed 2026-10-10 against the official
[Search API](https://docs.searxng.org/dev/search_api.html),
[container installation](https://docs.searxng.org/admin/installation-docker.html),
[search settings](https://docs.searxng.org/admin/settings/settings_search.html),
and [AGPL license](https://github.com/searxng/searxng/blob/master/LICENSE).
SearXNG requires no search subscription or JARVIS API key. Running it consumes
local resources and network access. Upstream engine terms/rate limits still apply;
some optional engines require keys and should remain disabled if not configured.
No specific upstream engine's availability is promised.

JARVIS POSTs form data to the reviewed `/search` endpoint with `format=json`,
`categories=general`, first page only, and the minimized query. `time_range` accepts
day/month/year; engines vary in support. There is no native guaranteed result-count
parameter: JARVIS validates and truncates the JSON `results` array locally. Domain
filters use documented `site:` syntax and independently filter normalized domains
because engines may ignore that syntax. Publication metadata is optional
`publishedDate`, never invented from rank or retrieval. Responses normalize title,
URL, domain, content snippet, publication, retrieval, rank and runtime result ID.
Extra provider-specific data is not allowed to become tool authority.

JSON output must be enabled in `settings.yml`; otherwise 403 is an honest
`SEARXNG_JSON_DISABLED_OR_FORBIDDEN`, with no HTML/paid/public-instance fallback.

## Current PC inspection

Docker and Podman were absent from PATH; Docker Desktop was absent from its checked
standard installation locations. WSL reports default version 2 but lists no installed
distribution. No Docker/WSL/SearXNG was installed, started, downloaded or configured.
Machine-level provisioning is pending explicit authorization and a workable runtime.
The following setup is prepared, **not executed or certified on this PC**.

### Authorized setup completed on 2026-10-10

The user installed and started Docker, then authorized the remaining local search
setup. Docker Desktop 4.94.0 / Engine 29.8.2 reports `desktop-linux`, linux/amd64.
No existing `jarvis-searxng` container, port 8080 listener, private SearXNG directory
or private web configuration was present. The setup below was then executed.

The official image is pinned to
`docker.io/searxng/searxng@sha256:85492ba800a861e3e8ff6014c430e81369fe6ca766a9990595f616d1ce95b272`.
SearXNG reports `2026.10.9-f4822b3fc`. Its published host port was independently
inspected as `127.0.0.1:8080`; restart policy is `no`. Private configuration/data
live in `%LOCALAPPDATA%\Jarvis\searxng`, with a fresh private secret and JSON enabled.
JARVIS's enabled private config is `%LOCALAPPDATA%\Jarvis\web.toml`.

A real POST JSON probe for `Python venv documentation` returned official Python
documentation and virtualenv results. Some upstream engines reported CAPTCHA or
rate limiting; none was bypassed. Initial startup also reported unavailable ahmia
and torch engines. Startup readiness must be checked before submitting a search:
the first probe during certificate initialization returned a closed connection;
a subsequent probe after the listening log succeeded.

The container is manually started and ephemeral (`--rm`); configuration/data
persist outside it. After a manual stop or Docker shutdown, start it again with
Docker running, using these commands (do not run while the named container exists):

```powershell
$jarvisSearchRoot = "$env:LOCALAPPDATA\Jarvis\searxng"
docker run --name jarvis-searxng --rm -d `
  --publish 127.0.0.1:8080:8080 `
  --mount "type=bind,source=$jarvisSearchRoot\config,target=/etc/searxng" `
  --mount "type=bind,source=$jarvisSearchRoot\data,target=/var/cache/searxng" `
  docker.io/searxng/searxng@sha256:85492ba800a861e3e8ff6014c430e81369fe6ca766a9990595f616d1ce95b272
docker logs jarvis-searxng
# Wait for the listening/worker startup log before testing JSON:
Invoke-RestMethod -Method Post -Uri 'http://127.0.0.1:8080/search' `
  -Body @{ q='Python venv documentation'; format='json'; categories='general' }
# Deliberate manual shutdown:
docker stop jarvis-searxng
```

The previous missing-runtime inspection is historical. A working API alone does
not establish JARVIS's full research/model gate; see `M3_5_TEST_REPORT.md`.

## Once a working Docker runtime is deliberately provided

Docker/WSL installation and consequential host configuration are separate setup,
not JARVIS runtime capabilities. Do not run an administrator installer or enable
Windows features automatically. Obtain explicit approval before agent-performed
host setup. Docker Desktop's own licensing/system requirements also need review if
that route is chosen. The user may supply an already working runtime instead.

In a normal PowerShell terminal, first inspect the existing runtime/container/port:

```powershell
docker version
docker ps -a --filter name=jarvis-searxng
Get-NetTCPConnection -LocalPort 8080 -State Listen -ErrorAction SilentlyContinue
```

Stop if the name, port or private directory belongs to an existing setup; inspect
and preserve it. The commands below intentionally refuse replacing an existing
directory. They require separate approval to download/run this infrastructure:

```powershell
$jarvisSearchRoot = "$env:LOCALAPPDATA\Jarvis\searxng"
if (Test-Path -LiteralPath $jarvisSearchRoot) { throw 'Existing setup: inspect before proceeding.' }
New-Item -ItemType Directory -Path "$jarvisSearchRoot\config","$jarvisSearchRoot\data" | Out-Null
$jarvisSearchRandom = [Security.Cryptography.RandomNumberGenerator]::Create()
$jarvisSearchBytes = New-Object byte[] 32
$jarvisSearchRandom.GetBytes($jarvisSearchBytes)
$jarvisSearchRandom.Dispose()
$jarvisSearchSecret = [BitConverter]::ToString($jarvisSearchBytes).Replace('-','')
@"
use_default_settings: true
server:
  secret_key: "$jarvisSearchSecret"
  limiter: false
search:
  formats:
    - html
    - json
"@ | Set-Content -LiteralPath "$jarvisSearchRoot\config\settings.yml" -Encoding UTF8
Remove-Variable jarvisSearchSecret
Remove-Variable jarvisSearchBytes
docker pull docker.io/searxng/searxng:latest
$jarvisSearchImage = docker image inspect docker.io/searxng/searxng:latest --format '{{index .RepoDigests 0}}'
# Record the inspected immutable image digest for the compatibility report.
docker run --name jarvis-searxng --rm -d `
  --publish 127.0.0.1:8080:8080 `
  --mount "type=bind,source=$jarvisSearchRoot\config,target=/etc/searxng" `
  --mount "type=bind,source=$jarvisSearchRoot\data,target=/var/cache/searxng" `
  $jarvisSearchImage
docker logs jarvis-searxng
Invoke-RestMethod -Method Post -Uri 'http://127.0.0.1:8080/search' `
  -Body @{ q='Python venv documentation'; format='json'; categories='general' }
# Manual shutdown; no restart policy or startup service:
docker stop jarvis-searxng
```

Only the search port is bound to host loopback, never all host interfaces. This
simple local-only single-container setup deliberately disables the public-instance
limiter, uses a fresh private secret and does not configure a reverse proxy, public
hosting, optional paid engines or automatic restart. It remains pending Windows
runtime/image compatibility validation. SearXNG itself manages upstream requests;
JARVIS's independent fetch restrictions apply to every selected result.

After validating your own running instance, copy `config/examples/web-searxng.toml`
to `%LOCALAPPDATA%\Jarvis\web.toml`, preserving any existing file. The example's
explicit authorization applies only to its exact local search endpoint. Run the
explicit JARVIS evaluation below with a new report name; an API probe alone is
not milestone qualification.
