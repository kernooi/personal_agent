# M3.5 network and evidence policy

Web research defaults off without `--web-config`. Currency and Windows permission
remain separate. Local inference retains the existing cloud-disabled Ollama setup.

| Operation | Allowed destination |
|---|---|
| Local inference | Existing fixed `127.0.0.1:11434` |
| SearXNG infrastructure | Exact private-config `http://127.0.0.1:<port>/search`, explicit separate authorization, never port 11434 |
| Public source retrieval | Validated public HTTPS, port 443 only; independently pinned DNS/socket peer |
| Currency | Existing fixed Frankfurter/ECB routes |

The model cannot select the search endpoint, request path, headers, cookies or
public fetch URL. Source selection uses runtime IDs. No consumer search HTML is
scraped by JARVIS. No arbitrary loopback/LAN exception exists in public fetching.

Public addresses exclude loopback, private, link-local, metadata/shared-address,
multicast, reserved, unspecified, mapped-private IPv4, site-local, 6to4 and Teredo.
Known NAT64 translation prefixes are also denied to prevent hidden IPv4 destinations.
Alternate numeric spellings fail URL syntax or checked resolution. All DNS answers
must pass; one selected numeric address is connected directly, actual peer must
match, and original hostname still supplies normal TLS certificate/SNI checks.
Environment proxies, redirects inherited from clients, credentials in URLs,
secret-looking URL query parameters and unsupported schemes are refused.
Redirects are manual and fully revalidated, default two hops. Each hop uses a new
client without carried cookies. No TLS verification bypass or retries exist.

Default bounds: two searches, five results each, three pages, 512 KiB per response,
1.5 MiB per task, 12,000 extracted characters, four model turns, 100 seconds overall
(also capped by the frozen model profile deadline), 12-second worker watchdog and
at most five-second connect/read waits. One worker per process and one active broker
task. Each page can perform up to three network requests including redirects.
Owned workers are polled for cancellation every 20 ms; only those workers can be
terminated. Worker process memory is capped at 512 MiB using a private Windows Job
Object; inability to establish the cap fails closed. No administrator privilege,
global network setting or service installation is needed for that process limit.

Unknown failed page fetches reserve their possible byte consumption conservatively.
Explicit measured failure receipts from the owned worker account consumed body
bytes: status refusals before reading the body report zero; completed downloads
retain measured bytes if extraction fails. Invalid counts cannot refund a
reservation. Timeouts/unmeasured failures retain the full reservation.
Successful receipts account actual bytes; remaining budget constrains subsequent
workers. Available evidence can produce labelled partial research on byte exhaustion.
No newly admitted request occurs after stop; sent requests cannot be retracted.
An expired/cancelled task cannot publish a late answer. No interrupted read is replayed.

Supported content: UTF-8 HTML/plain text and text PDFs with identity or bounded
gzip HTTP encoding. Other encodings, executable/binary formats, blocked pages and encrypted
PDFs fail honestly. HTML scripts/styles/nav/hidden/form/iframe content are inert and
removed where practical; malformed-page boilerplate extraction remains heuristic.
PDF parsing uses locked pypdf, maximum 15 pages, bounded content streams, the same
worker watchdog/memory cap, and no OCR, attachment following, JS or document launch.
Canonical URLs are metadata only and are never automatically fetched.

Queries contain only the current sanitized owner topic. Model refinements cannot
introduce other terms; source/page text cannot generate a second destination or
query. No conversation history, local file/memory, Notepad content, screenshots,
cookies or credentials are supplied to the provider. Known private patterns block
the request; this is not a guarantee of recognizing every secret a user explicitly
types into an otherwise public-looking question. Future private disclosure requires
separate design and authorization. A local SearXNG instance still sends the approved
public query to its configured upstream engines; self-hosting does not mean offline.

This boundary trusts the local OS, configured search infrastructure, installed
packages and certificate store. It does not attest a compromised machine, provider
truth, hidden OS routing, or perfect extraction/semantic interpretation. No claim of
physical network isolation is made. External instructions cannot widen permissions.
# Live compatibility follow-up: bounded gzip

Public fetches still request `Accept-Encoding: identity`. If a public source
nevertheless responds with gzip, its raw wire body is capped at the configured
response byte limit before bounded zlib decompression. The decoded body has the
same separate byte ceiling. Malformed/truncated gzip, extra/trailing streams,
concatenated members and other encodings fail closed. Download receipts retain
actual wire bytes and separately record decoded bytes and encoding. The existing
worker memory/watchdog, TLS, DNS/peer, redirect, cancellation and total download
limits still apply. This replaces the initial identity-only response rule.

## Source-selection follow-up

Alternatives are limited to the current task's validated search result IDs/URLs.
The model ranks candidates; the runtime considers remaining returned results,
prefers domain diversity, deduplicates URLs, and puts common social shells and
selected derivative encyclopedias later. This is a fetch preference, not a domain
permission or proof of reliability. Owner-supplied URLs bypass this ranking but
retain the same public URL/network policy. Every attempt, including failed or
cached candidates, counts against the configured page-attempt ceiling. New reads
retain fresh broker admission/cancellation checks and durable intent.

For who-is topics, the controller offers an optional biography/profile refinement
containing only the authorized topic plus those fixed descriptive words. The model
must select an exact controller-approved query; arbitrary additional words and
source-provided search instructions are rejected. This replaces the initial
verbatim-owner-word-only refinement rule without disclosing private context.
Retrieved paragraphs are ranked for topical words and numerical size descriptions
before evidence/context trimming. Citation indexes remain bound to stored original
text. A lightweight world-superlative check rejects excerpts lacking a superlative
and numeric detail; it does not prove a worldwide record or full semantic relevance.

The existing hard ceilings remain. This PC's backed-up private configuration now
uses 8 results per query, 5 page attempts, 1 MiB per page and 3 MiB total. Model
context/output, 4 model turns, 100-second task deadline and 12,000 extracted text
characters remain unchanged. Existing conservative checked-in defaults remain.
