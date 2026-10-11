# M4 browser compatibility

Observed on 2026-10-11: Windows NT 10.0.26200.0, Python 3.13.2, installed stable
Google Chrome 154.0.8037.98, valid Google LLC Authenticode signature at
`C:\Program Files\Google\Chrome\Application\chrome.exe`.
Executable SHA256: `6849d2982038de9f9489a7b3858f3b785b7fec06a842c93c517281d21995c8ca`.
Automation dependency: Playwright 1.63.0; greenlet 3.5.6; pyee 13.0.1.
All are locked with hashes and installed only in `.venv`. No browser was downloaded.

Playwright documents branded [installed browser channels](https://playwright.dev/python/docs/browsers)
and a [persistent context](https://playwright.dev/python/docs/api/class-browsertype).
JARVIS pins the executable as well as the Chrome channel, keeps the Chromium
sandbox enabled, and uses a dedicated user-data directory. Existing default Chrome
profiles are unsupported. Chrome updates invalidate the registration; inspect and
re-register manually rather than silently trusting a new executable.

The private profile is `%LOCALAPPDATA%\Jarvis\browser\chrome`. Registration is
`%LOCALAPPDATA%\Jarvis\chrome-registration.json`. Creation is exclusive and never
overwrites an existing profile or registration. Registration pins the binary, not
account ownership or service entitlement. Only that launched context can close.

Limits: at most two owned service tabs; at most five results; query 256 characters;
RPC replies 32 KiB; operation deadline 20 seconds (configurable 2–30); references
expire after 300 seconds (10–600). Restored nonblank tabs require manual review.
No arbitrary browsing, downloads, uploads, extensions, generated code/selectors,
CAPTCHA/DRM bypass or login form filling.

Network routing validates all DNS answers for each routed HTTPS request, rejects
local/private addresses and restricts main navigation to the selected service.
Public subresources remain necessary for media/CDNs. This is application-level
filtering, not an OS firewall: Chromium's DNS peer is not pinned to the validated
answer, and background traffic is not fully attested. No new system-wide settings
or proxy installation was performed. Public research retains its separate stricter
trusted fetch transport and never inherits browser cookies.

The attended YouTube report `evaluations/m4-windows-youtube-v1-r6.json` passed with
the actual local model and native hotkey. Launch-only autoplay permission in the
dedicated profile allowed the ad to finish naturally; no global Chrome preference
or ad-skipping control changed. Overall compatibility remains NOT FULLY VERIFIED:
Spotify/Netflix setup and normal-Chrome coexistence are pending. Offline tests
cannot establish website compatibility. Layout, consent, login, ads, geography and
player errors can block later runs. Failed optional-resource DNS is aborted without
being mistaken for a private destination; private/origin rejection still stops.
