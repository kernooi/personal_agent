# ADR 0004 — M3.5 public research and local SearXNG

Accepted scope: the user's M3.5 request and subsequent SearXNG clarification.
Implementation is in progress; live search qualification is pending.

Retain the existing broker. A controller-owned owner-topic hash, session, revision,
grant and exact prepared `web.research` action bind one bounded research job.
The existing durable intent precedes model planning and network activity. Every
search/fetch rechecks broker admission, cancellation, deadline and configuration,
and journals a read intent before the worker. Public-read interruptions fail
without automatic replay and without acquiring the Windows unknown-effect latch.
Neither external text nor the research model can propose Notepad operations.

Search infrastructure and public source fetching are distinct permissions.
The initial replaceable `SearchProvider` is `SearXNGProvider`; no commercial key,
paid API, random public instance or provider switching is required. Configuration
permits one explicit numeric loopback `/search` endpoint, excludes Ollama's port,
and requires `local_search_authorized`. This exception is unavailable to public
URL tools. Future provider adapters belong at composition/configuration boundaries,
not in research logic, evidence or Windows policy.

The local model proposes queries containing only authorized owner-topic terms,
selects normalized runtime result IDs, and selects retrieved source/excerpt IDs.
Whole outputs have separate strict schemas; extra tools/permissions/URLs/claims
are invalid. Search egress receives no history, files, Notepad state or retrieved
page text. Private-looking owner requests fail closed before a provider call.
This conservative filter is not comprehensive secret detection; no future private
disclosure permission has been implemented.

Source URLs are controller-resolved result IDs or separately validated owner URLs.
Public HTTPS uses bounded supervised workers, normal TLS, checked public DNS and
pinned numeric connections with actual peer checks. Each redirect gets the same
checks. Search snippets are selection data, never factual evidence. HTML/plain/PDF
are inertly extracted. The model gets bounded labelled external excerpts, not HTML.

Factual rendering is deliberately extractive: the model selects an excerpt index,
and runtime renders the original retrieved text and its source. This prevents the
quote alteration observed in the first live test. It proves excerpt provenance,
not source truth, relevance or full semantic entailment of unrestricted paraphrases.
Publication/update dates remain nullable; retrieval never substitutes for them.
Conflicts/insufficiency are model assessments, constrained to existing evidence;
conflict output requires two distinct fetched sources. They are not an independent
universal fact checker. Today requests without today's dated evidence are labelled
insufficient. Universal latest-event ordering remains an open qualification limit.

Eight-entry search and extracted-document caches are separate, session-only,
public-only, with original timestamps and ten-minute default TTL. They contain
no raw owner query or conversation; interpretation/provider/filter inputs bind
hashed keys. Refresh bypasses caches; cache clear does not replay or erase evidence.
Raw HTML/PDF is discarded in the worker after extraction. The private existing
journal stores typed hash bindings and public excerpts/receipts, not raw prompts.

No M4 browser/media, shell, generated code, uploads, account login, GUI navigation,
cookies, cloud inference or additional Windows capability is introduced.
