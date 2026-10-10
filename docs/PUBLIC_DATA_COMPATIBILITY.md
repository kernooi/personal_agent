# M3 public currency provider and limits

Reviewed on 2026-10-10 against [Frankfurter's official v2 documentation](https://frankfurter.dev/),
the provider metadata endpoint `https://api.frankfurter.dev/v2/providers/ecb`,
and its generic provider-specific pair route. The actual metadata advertises 45
canonical codes, including historical currencies. Coverage is not a promise of a
fresh quote: old/missing pair data fails the same freshness gate. This is the
RTX 4070 / 32 GB desktop, not a newly provisioned laptop.
No account, key, paid service, extra model or inference provider was added.

## Selected provider

The replaceable `CurrencyProvider` interface receives only validated base/quote,
reviewed policy, cancellation and deadline. `FrankfurterProvider` uses precisely:

| Operation | HTTPS GET path on `api.frankfurter.dev:443` |
|---|---|
| Supported currency metadata | `/v2/providers/ecb` |
| Any validated supported pair | `/v2/providers/ecb/rate/{base}/{quote}` (lowercase codes) |

These are provider-specific routes, not Frankfurter's default blended endpoint.
The response has `date`, `base`, `quote`, `rate`; the unit is one base currency.
Frankfurter derives each requested pair from ECB euro reference observations.
JARVIS preserves the returned pair's decimal precision; it does not invert the
other rounded pair or calculate a cross-rate itself. The two returned rounded
rates therefore need not be exact reciprocals. No local inversion or cross-rate
fallback is implemented; missing, conflicting or dated observations cannot be
combined into a fabricated pair. Historical date selection, alternative providers
and buy/sell quotations are not implemented.

Frankfurter publishes daily reference information. The
[ECB explains its reference-rate schedule](https://www.ecb.europa.eu/stats/policy_and_exchange_rates/euro_reference_exchange_rates/html/index.en.html):
normally around 16:00 CET on working days, excluding TARGET closing days.
The API supplies an effective **date**, not an exact publication instant or
source timezone. A Saturday fetch can legitimately return Friday's observation.
JARVIS does not label these as live trading prices or executable bank/card/cash rates.

Frankfurter's documentation permits free commercial use without keys, subject
to underlying provider terms, and describes abuse rate limiting without a fixed
published quota. The ECB's
[use/disclaimer terms](https://www.ecb.europa.eu/services/using-our-site/disclaimer/html/index.en.html)
apply to its data. Answers attribute both Frankfurter and ECB, link both canonical
sources, and disclose the provider's pair derivation and JARVIS's local conversion.
This does not imply ECB endorsement. There are no trades, transfers or payments.

## Network enforcement

Public data, local inference and Windows execution are three separate decisions.
No selected public-data configuration means no currency fetch. An explicitly
selected `mode = "enabled"` permits the reviewed metadata and generic pair routes.
Disabled mode refuses
current lookup even if a cache exists; explicit fixture mode is for injected
synthetic test providers, never a live-failure fallback. Windows remains simulated
unless all existing M2 real/attended/registration/qualification conditions are met.

The public transport enforces HTTPS, exact lowercase host, implicit port 443,
exact paths, GET, no query/fragment/credentials, no redirects, normal certificate
verification, and no environment proxies or custom proxy configuration.
Its only application headers request JSON and identity encoding; the standard
HTTP client also sends protocol headers. The pair is in the public path. The
provider sees the connecting public IP and request timing, but receives no amount,
owner message, history, local model identity, Notepad content, files or credentials.

DNS answers must all be public addresses. Loopback, private, shared-address space,
link-local, metadata, multicast, reserved and unspecified addresses are rejected,
including IPv6 equivalents, mapped private IPv4, site-local, 6to4 and Teredo.
The adapter connects to the checked numeric address and checks the **actual socket
peer** against it. HTTPcore still uses the original hostname for TLS SNI and normal
certificate verification. This closes the check/connection DNS substitution gap;
it is not an earlier hostname-only check.

This uses the locked HTTPX 0.28.1 / HTTPcore 1.0.9 synchronous transport and its
reviewed `_pool._network_backend` integration. Other versions fail closed until
reviewed. Both dependencies are now explicitly pinned; lock regeneration changed
only HTTPcore's dependency attribution, not installed package versions.

One disposable, hidden worker runs a fixed installed module, not model code or a
shell command. The supervising process bounds the entire job, including DNS,
and polls cancellation every 20 ms. A worker watchdog also bounds DNS if the
supervisor disappears. Only this owned worker can be terminated; Notepad and
Ollama are never killed. HTTP connect/read timeouts are at most five seconds;
overall policy defaults to 12 seconds (allowed 1–20). Cleanup can add up to three
seconds without starting another request. Maximum accepted JSON is 8 KiB by
default (hard config ceiling 16 KiB). Integer/decimal precision and exponent bounds
are checked before decimal expansion. Duplicate keys, extra fields, error pages,
compression and malformed data are rejected. Worker input/output are separately bounded.

Concurrency is one public worker per JARVIS process and one active broker task.
Separately launched processes have separate limits. There are **zero automatic
retries**, including HTTP 429: return `RATE_LIMITED` promptly; `Retry-After` cannot
cause a sleep beyond the task deadline. A later explicit request is a new task.
Cancellation or deadline expiry after a fetch suppresses publication. A public
request already sent cannot be retracted. A crashed read is ended without automatic
replay or the desktop unknown-outcome latch; Windows recovery remains unchanged.

These controls trust the local OS, installed packages, CA trust and repository.
They do not attest a compromised machine, prove that provider information is
economically correct, exclude OS-level interception, or establish continuous
network isolation. No network settings are changed by JARVIS.

## Evidence, freshness, arithmetic and cache

The adapter owns source IDs and UTC retrieval/expiry timestamps. The normalized
strict quote records preserve pair, one-unit basis, decimal rate, provider and
actual provenance, canonical URLs, effective date/precision, validation,
sensitivity, freshness and interpretation version. Returned records and cache
records are independently checked before publishing. The model never receives
provider response text as instructions and cannot select URLs, headers, permissions,
source IDs, final rate values or calculated results.

Latest requests accept source dates no more than seven calendar days old by
default, reject future dates, and explicitly say **latest available daily reference**.
This is a conservative age bound, not a market-holiday calendar or a guarantee
that the upstream API has already published every scheduled update. Retrieval
timestamps are also displayed in Asia/Kuala_Lumpur (UTC+08:00 for these contemporary
observations); the source date is not converted into a made-up precise timestamp.

Amounts are decimal strings, finite and nonnegative, from zero through
1,000,000,000,000; rates must be positive and no greater than that bound.
At most 24 significant digits and 12 decimal places are accepted. Valid comma
grouping is normalized. Calculations use decimal precision 64 (enough for the
exact product of two accepted 24-digit values) and round only
at final display with half-even: JPY to whole yen, all other currencies to two
decimal places. This is a display policy, not a complete ISO minor-unit catalogue.
Explicit supplied rates are calculated locally, labeled user supplied, and have
no public citation. A source follow-up after one asks for a sourced rate first.
Reverse rates come from the reverse provider route, not an unrecorded inversion.

The public cache key includes interpretation version, provider, mode, reference
basis, latest selection and pair. The cache stores quotes only, with no personal
amounts or conversations. Default TTL is one hour, default bound eight records;
the bound applies across all pairs. Refresh bypasses fresh cache. Source follow-ups reuse
the session's actual observation and ID without fetching or changing timestamps.
Expired session evidence is labeled historical rather than current.

Stale fallback is off by default. With explicit `allow_stale_cache = true`, an
eligible provider failure can return a validated dated quote within the configured
stale/observation-age limits. Its original retrieval time is retained; the answer
discloses the failure and says not verified current. Cancellation and destination
policy rejection do not fall back. No synthetic quote substitutes for failure.
Invalid persistent cache files are not served or silently overwritten; persistence
is disabled for that instance so the original file can be inspected manually.

Interactive cache controls: `/cache`, `/cache-clear`, `/refresh-rate`, each on
its own line. Public cache and M3 simulation journal are private in
`%LOCALAPPDATA%\Jarvis\public-quotes-v2.json` and `m3-journal.sqlite`.
Raw prompts and full chat history are not journaled; history remains bounded in
memory. The journal necessarily stores typed action arguments, including the
local amount, and rendered results for task identity/recovery; these remain local
and never enter the public quote cache or public request.

## Generic coverage and local-only calculations

`supported_currencies()` uses the same supervised, pinned HTTPS transport for the
fixed documented ECB metadata endpoint. It validates provider key/name, reference
basis, original source, EUR pivot, an empty unknown-currency list, and 1–256 unique
uppercase three-letter codes. It sends neither pair nor amount for metadata.
Additional provider informational fields are ignored and never model instructions.
No giant manual support list, pair-specific functions or exhaustive live matrix exists.

The separate `public-currencies.json` cache records provider, interpretation version,
source URL, coverage, synthetic/public origin, UTC retrieval and expiry. TTL defaults
to 24 hours (configurable 1 second–7 days). Expired/malformed metadata is not served;
invalid files are preserved. A latest-rate request retrieves needed metadata only
after broker admission, before disclosing a validated pair. Metadata failure stops
the pair request; stale quotes cannot bypass an unavailable support catalogue.
Same-currency and supplied-rate calculations require valid cached membership and
never fetch, even with retrieval enabled. If coverage is absent/expired, request a
latest rate separately to refresh it. This resolves the requirement to validate
provider support without silently fetching for an explicitly local calculation.

Alias normalization is a small reviewed vocabulary, independent of coverage;
every provider-supported code works without changing aliases/source. Other names
need canonical codes. Unknown/syntactically invalid identifiers, unspecified dollar
and ambiguous symbols, multiple pairs and unsupported historical dates fail safely.
Numeric followups require the immediately preceding unambiguous controller context;
intervening chat, ambiguity, errors or another session clears that reference.
Private config is preserved; the new TTL has a backwards-compatible default.
The old v1 quote cache and all evaluation evidence remain untouched.
