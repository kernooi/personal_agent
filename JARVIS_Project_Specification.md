# JARVIS: Model-Agnostic Local Personal Agent

**Document version:** 2.0 - fresh-start specification  
**Date:** 9 October 2026  
**Status:** Proposed architecture and implementation contract; not an implemented or security-audited product  
**Target:** One user's Windows desktop session, local inference, local personal data, controlled online integrations  
**First implementation task:** M0 only  
**Companion:** `JARVIS_Codex_First_Prompt.md`

> Build one dependable assistant with replaceable models, not an application whose permissions and behavior depend on a particular model. The model proposes. Trusted code validates, authorizes, executes, and verifies. The user can interrupt.

## How to use this specification

This document is self-contained. Use it as the project specification for the new repository instead of combining it with the earlier JARVIS architecture documents. The earlier files need not be deleted, but they are not additional implementation requirements for this restart.

Read the whole specification before making architectural decisions. Implement only the currently approved milestone. A description of a future capability is not authorization to implement or enable it now.

- **MUST / MUST NOT:** required acceptance conditions for the milestone where a feature becomes relevant.
- **SHOULD:** the default design; deviations need a recorded architecture decision.
- **Candidate:** a component or model to evaluate, not a compatibility or performance guarantee.
- All timeout values, budgets, and quality thresholds below are proposed starting settings, not measurements from the user's computers.
- Code, command names, schemas, and configuration illustrate the JARVIS design. Unless identified as an existing external command, they are interfaces to implement, not software already installed.
- External technology facts have source references. Architectural rules are project decisions, not features provided automatically by the cited libraries.

Keep `AGENTS.md` concise: the current scope, invariant rules, commands, and a pointer here. Codex recognizes repository `AGENTS.md` instructions; this detailed specification is read through an explicit instruction, not because its filename has special meaning. [S01]

## Contents

- [1. Product definition and actual hardware context](#1-product-definition-and-actual-hardware-context)
- [2. Capability roadmap and user experience](#2-capability-roadmap-and-user-experience)
- [3. Architectural decisions](#3-architectural-decisions)
- [4. Core structure and trust boundaries](#4-core-structure-and-trust-boundaries)
- [5. Repository and development conventions](#5-repository-and-development-conventions)
- [6. Domain contracts](#6-domain-contracts)
- [7. Model-agnostic implementation](#7-model-agnostic-implementation)
- [8. Configuration and hardware profiles](#8-configuration-and-hardware-profiles)
- [9. Task lifecycle and bounded execution](#9-task-lifecycle-and-bounded-execution)
- [10. Durable state, deduplication, and recovery](#10-durable-state-deduplication-and-recovery)
- [11. Permissions, consent, and data-flow rules](#11-permissions-consent-and-data-flow-rules)
- [12. Concurrency, cancellation, and user ownership](#12-concurrency-cancellation-and-user-ownership)
- [13. Windows and general application interaction](#13-windows-and-general-application-interaction)
- [14. Browser, media, and games](#14-browser-media-and-games)
- [15. Fresh information and web research](#15-fresh-information-and-web-research)
- [16. Screen understanding and Wordle](#16-screen-understanding-and-wordle)
- [17. Voice, memory, and personal context](#17-voice-memory-and-personal-context)
- [18. Routines, scheduling, files, and future integrations](#18-routines-scheduling-files-and-future-integrations)
- [19. Setup, local-model connection, and moving computers](#19-setup-local-model-connection-and-moving-computers)
- [20. Testing, model evaluation, and release gates](#20-testing-model-evaluation-and-release-gates)
- [21. Milestones and concrete deliverables](#21-milestones-and-concrete-deliverables)
- [22. Working with Codex without losing scope](#22-working-with-codex-without-losing-scope)
- [23. Non-negotiable implementation rules](#23-non-negotiable-implementation-rules)
- [24. First Codex prompt](#24-first-codex-prompt)
- [25. Sources and verification notes](#25-sources-and-verification-notes)

## 1. Product definition and actual hardware context

### 1.1 The intended assistant

JARVIS is a persistent personal assistant that can converse, understand a permitted view of the desktop, remember approved context, obtain current information, and operate supported applications. It should feel like one assistant even when its internal model or hardware changes.

Representative requests:

- "Open Spotify and play some relaxing music."
- "Find that video on YouTube and play it."
- "Look for this series on Netflix."
- "Launch my game and apply gaming mode."
- "What is the current MYR to JPY exchange rate?"
- "What am I looking at? What should I guess in Wordle?"
- "Open my editor, find this project, and explain the error."
- "Stop", "pause", "what have you done?", and "undo the changes you can safely undo."

The product target is **broad, increasingly tested computer assistance**, not perfect control of every possible application. Reliability and observable limitations matter more than a theatrical personality.

### 1.2 Do not confuse the two computers

| Environment | User-provided information | Development consequence |
|---|---|---|
| Current development laptop | Lower-spec Windows laptop; exact CPU, GPU, and RAM unknown; previously using `qwen3:1.7b` | Default to fake-model tests; later reuse a suitable small local model. Do not assume desktop resources are available. |
| Future main PC | RTX 4070, 32 GB system RAM, Ryzen 5 5600X | Use the same code with a separately evaluated local model profile. Verify actual VRAM and available memory on that machine. |

Do not assume the laptop has 32 GB RAM. Do not infer RAM generation. Do not promise a GPU fit from model download size alone. GPU context and runtime overhead also matter; Ollama documents that larger context lengths increase memory demand. [S07]

### 1.3 The three meanings of local

1. **Local inference:** text, vision, speech, and embeddings run on the user's machine using installed artifacts. No silent cloud fallback.
2. **Local personal storage:** memory, task history, preferences, and sensitive artifacts remain on that machine unless the user explicitly exports them.
3. **Controlled online tools:** approved web searches, exchange-rate providers, Spotify, YouTube, and other online services use the internet. Necessary queries and normal browser traffic reach those services.

"Local-first" does not mean "all features work without the internet" or "external websites cannot see requests." During M0, runtime networking is absent. During M1, the only inference connection is to the configured local model service; online tool integrations arrive later.

Codex is a development assistant. JARVIS MUST NOT require Codex, a cloud API key, or a ChatGPT account as a runtime dependency. The privacy of development sessions is separate from the privacy of the finished local application.

### 1.4 Explicit initial non-goals

Do not initially implement administrator automation, unrestricted shell execution, unattended purchases, credential extraction, automated login challenges, competitive-game input automation, remote internet-facing control, self-installing skills, or a background agent that constantly records the screen.

The user's wish for broad application interaction is not blanket permission for irreversible operations, uploads, messaging, purchases, or changes to security controls.

## 2. Capability roadmap and user experience

| Capability family | Intended behavior | Important boundary |
|---|---|---|
| Applications and windows | Register, launch, focus, arrange, and gracefully close supported apps | Never discard unsaved work or force-kill an app implicitly |
| Browser and media | Search, open results, play/pause, inspect supported playback state | Logged-in state is sensitive; service support and restrictions vary |
| Games | Launch registered games; set approved audio/notification routines | No injection, anti-cheat bypass, or autonomous gameplay in the initial product |
| Current information | Retrieve sources, compute values, cite and timestamp answers | A model's recollection is not evidence for a current fact |
| Screen assistance | On-demand selected-window capture; explain visible UI; help with puzzles | Advice does not authorize mouse/keyboard input |
| Conversation and voice | Local text, then push-to-talk, speech output, optional wake word | Ambient audio and wake words are not authority for consequential actions |
| Personal memory | Inspectable preferences, task context, notes, and later retrieval | Do not silently turn observations or conversations into permanent memory |
| Routines | Repeat approved, parameterized workflows with verification | A routine cannot grant itself privileges |
| Files and coding | Scoped search, explanations, previews, later controlled edits/tests | Repository tests and generated code are executable, not harmless data |
| Scheduling and monitoring | Approved events, reminders, no-focus-stealing notifications | A sleeping or powered-off host cannot execute ordinary local work |
| Communications and calendar | Later read/draft/schedule integrations | Sending or changing external state needs explicit authority |
| Remote and smart-home access | Future authenticated adapters | Separate threat model; disabled until deliberately implemented |

The interface must expose the active model/profile, real versus simulated tools, current task, progress, pending approvals, cancellation, and what remains unverified. Normal low-risk operations inside a narrow approved scope should not require a confirmation for every internal step.

A good refusal or partial outcome is useful: "I opened the result, but playback is blocked by a login dialog" is better than a false "Done."

## 3. Architectural decisions

| Decision | Project default | Why |
|---|---|---|
| Application shape | Modular Python application | Small enough for one developer and a lower-spec laptop |
| Process model | One process for M0/M1; supervised native workers when needed | Avoid premature distributed systems; contain blocking native operations later |
| Model runtime | Ollama first, behind an interface | Native Windows runtime exists; models remain replaceable [S02] |
| Model strategy | One configured text model at a time initially | Portability without expensive automatic routing |
| Proposal format | One versioned internal decision contract | Execution does not depend on provider wire formats |
| Planner | One bounded planner per task | No competing autonomous agents sharing the same desktop |
| Execution | Deterministic task runtime and permission broker | The model never directly executes tools |
| Storage | SQLite on local disk and a private artifact directory | Durable state without an external database service |
| Frontend | Terminal first; native tray/approval UI later | Validate behavior before designing the visual shell |
| Desktop actions | Registered adapters, UI Automation/Win32, constrained visual fallback | Prefer identifiable controls over blind coordinates [S10] |
| Browser | Dedicated managed profile with Playwright | Explicit ownership and separate authentication state [S13] |
| Knowledge | Freshness-aware, evidence-backed retrieval | Prevent unsupported claims about live information |
| Expansion | Reviewed adapters and declarative routines | No runtime-generated privileged Python |
| Cloud inference | Not implemented | Preserves the stated local-only inference requirement |

Do not add Kubernetes, Redis, a message broker, a vector database server, multiple UI frameworks, or a multi-agent framework in M0/M1. Add infrastructure only to solve an observed problem.

Keep these concepts separate:

- **Provider:** software transport/runtime, such as Ollama.
- **Model artifact:** weights and quantization, such as an installed Qwen variant.
- **Model profile:** task role, prompt/schema versions, limits, runtime options, and evaluation record.
- **Capability:** a trusted JARVIS operation with effects, scope, and a verification contract.
- **Adapter:** the concrete implementation of that capability against fake state, Windows, a browser, or a service.

Changing a model does not change the adapter implementation or give the model additional authority.

## 4. Core structure and trust boundaries

### 4.1 Logical architecture

```text
User text / later voice and desktop shell
                  |
        Request and consent boundary
                  |
    Task runtime, context, budgets, history
          |                       |
          |               Model gateway
          |                  -> provider adapter
          |                  -> configured local model
          |                       |
          +---- candidate decision+
                  |
       Strict parser and tool registry
                  |
    Trusted broker: scope, effects, policy,
       approval, freshness, cancellation
                  |
       Durable dispatch intent / journal
                  |
   Fake adapters -> later Windows / browser /
           public-data / media adapters
                  |
       Independent observation / verifier
                  |
        Evidence-backed task outcome
```

The arrows are application data flow, not an invitation to let the model call operating-system APIs directly.

### 4.2 Module dependency rules

- `domain` contains standard-library types and business invariants. No Ollama, GUI, HTTP, or database SDK imports.
- `core` depends on interfaces and domain types, not concrete integrations.
- `models` translates provider responses; it does not execute actions or create approvals.
- `policy` authorizes already resolved effects; it does not ask the model whether an action is safe.
- `tools` owns the registry, preparation, broker dispatch, and verification coordination.
- `adapters` contain trusted integration code and normalized observations.
- `storage` persists state; a database write must not itself launch an external action.
- `ui` submits requests and decisions; it cannot bypass the broker.
- The composition root wires implementations. Other modules must not construct hidden global clients.

For M0, a few well-named modules are enough. Split files when responsibilities require it, not to mirror every future diagram.

### 4.3 Physical boundaries when real integrations arrive

Desktop and audio workers run in the logged-in user's interactive session, without elevation. Do not use a Session 0 Windows service as the desktop clicker. Microsoft documents the separation between services and interactive desktops. [S11]

Use supervised worker processes for UI Automation calls or native libraries that may hang. Give workers bounded requests and deadlines. A subprocess, Python virtual environment, working directory, or local IPC token is **not** a security sandbox. Host adapters remain trusted code.

Prefer parent-owned IPC or named pipes with restricted access. Validate message version, length, peer/session identity, request ID, and deadline. Do not deserialize pickle. Sensitive artifacts are referenced by broker-issued opaque IDs, not model-chosen paths.

M0/M1 need no HTTP control server. Any later local HTTP interface requires authentication, request-origin controls, no wildcard CORS, and CSRF/DNS-rebinding defenses. Loopback binding alone is not authentication.

### 4.4 Threat model and honest limits

Protect personal files, authenticated sessions, secrets, model context, actions, memory, and the user's ability to stop the system. Assume pages, app labels, model output, screenshots, tool responses, downloaded files, and saved notes can contain misleading instructions.

Do not claim resistance to malware already running as the same user or to a compromised operating system. The broker reduces accidental and model-induced misuse; it is not a replacement for OS security.

## 5. Repository and development conventions

### 5.1 Initial repository

```text
JARVIS/
  JARVIS_Project_Specification.md
  AGENTS.md
  README.md
  pyproject.toml
  requirements-dev.lock             # generated, not manually guessed
  .gitignore
  config/
    defaults.toml
    examples/
      laptop.toml
      desktop.toml
  docs/
    IMPLEMENTATION_PLAN.md
    BUILD_LOG.md
    decisions/
  src/jarvis/
    __init__.py
    __main__.py
    cli.py
    bootstrap.py
    domain/
    core/
    models/
    policy/
    tools/
    adapters/fake/
    storage/
  tests/
    unit/
    integration/
    fixtures/
```

These are target paths, not pre-existing code. Create only files needed by M0. Add `adapters/windows`, browser, audio, perception, memory, and evaluation modules in their milestones. Do not generate hundreds of empty files.

### 5.2 Language and dependencies

Choose Python 3.12 as the initial project baseline. An already installed Python 3.11 may be used if the developer records and tests that choice. Do not globally upgrade Python just to bootstrap M0.

M0 needs the standard library, Pydantic at input/configuration boundaries, and a small test/check set such as pytest and Ruff. Use `argparse`, `asyncio` where needed, `dataclasses`, `sqlite3`, and `tomllib` before adding equivalents.

M1 adds an HTTP client such as HTTPX. Desktop/browser/audio packages are later optional dependency groups. Do not install GPU speech stacks during basic text-agent development.

Resolve actual package versions and generate one lock strategy. A practical pip-based workflow is a `pyproject.toml` plus a generated development lock using pip-tools. Record the resolver and Python/platform used; regenerate or maintain platform-specific locks when needed. Never invent hashes or claim a cross-platform lock was tested on Windows when it was only tested elsewhere.

### 5.3 Portable configuration and private data

Commit schemas, source, synthetic fixtures, example profiles, and redacted evaluation summaries. Keep machine-specific executable paths, databases, logs, model caches, screenshots, audio, browser profiles, credentials, and `.env` files out of Git.

Use a per-user application data directory, such as `%LOCALAPPDATA%\Jarvis`, outside the repository. Tests use temporary directories. A `.gitignore` rule is not a secrecy boundary; check for accidentally tracked files before publishing.

### 5.4 Implementation records

`docs/IMPLEMENTATION_PLAN.md` owns planned milestone tasks. `docs/BUILD_LOG.md` owns observed evidence: commands run, actual results, platform, and gaps. Do not maintain several competing progress checklists.

An architecture decision records context, decision, rejected alternatives, consequences, and affected tests. Implementation agents must not silently relax the specification to make a test pass.

## 6. Domain contracts

### 6.1 Objects and ownership

| Object | Required meaning | Trusted owner |
|---|---|---|
| `UserRequest` | Request text, source, session, received time, selected context | UI/controller |
| `Task` | Goal, approved scope, revision, lifecycle, deadline, budget | Task runtime |
| `ModelRequest` | Relevant messages, response schema, profile snapshot, request ID | Model gateway |
| `ModelReply` | Parsed candidate decision plus usage/provenance | Provider + parser; still not authority |
| `ActionProposal` | Capability ID and typed arguments | Untrusted candidate |
| `PreparedAction` | Resolved target, effects, preconditions, required leases, action digest | Broker |
| `Grant` | Allowed effects/resources, issuer, limits, expiry, revocation version | Consent/policy subsystem |
| `Approval` | Exact action digest, task revision, human decision, expiry, consumed state | Consent subsystem |
| `ExecutionAttempt` | Dispatch attempt, start/end, observed outcome, uncertainty | Broker/adapter |
| `Evidence` | Postcondition, source, target, observation time, result | Verifier |
| `TaskResult` | Verified outcomes, unmet goals, partial effects, uncertainty | Task runtime |
| `ModelQualification` | Artifact/profile versions and capability-specific evaluation evidence | Evaluation harness |

Request ID, logical task ID, logical action ID, and attempt ID are different. Retrying a transport operation must not create a fresh logical instruction to repeat an external effect.

### 6.2 The first decision contract

Use a discriminated union with four branches:

| Kind | Fields | Meaning |
|---|---|---|
| `say` | `text` | Conversational content, not proof that an action happened |
| `clarify` | `question` | Request missing information without executing |
| `unsupported` | `message` | Current capabilities cannot meet the request |
| `propose_action` | `action` | One candidate operation to validate and authorize |

No `permission`, `approved`, `admin`, endpoint, executable path, action ID, or task revision is accepted from model-generated fields. These are controller-owned.

**Illustrative M0 boundary implementation:** a parser, not the full broker. It rejects duplicate JSON keys and unknown fields, and uses Pydantic strict validation. Pydantic strict mode reduces coercion; it does not supply authorization or semantic correctness. [S09]

```python
import json
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter


class StrictRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class OpenAppArguments(StrictRecord):
    app_id: str = Field(pattern=r"^[a-z0-9][a-z0-9._-]{0,63}$")


class OpenAppAction(StrictRecord):
    capability: Literal["apps.open"]
    arguments: OpenAppArguments


class Say(StrictRecord):
    kind: Literal["say"]
    text: str = Field(min_length=1, max_length=2000)


class Clarify(StrictRecord):
    kind: Literal["clarify"]
    question: str = Field(min_length=1, max_length=1000)


class Unsupported(StrictRecord):
    kind: Literal["unsupported"]
    message: str = Field(min_length=1, max_length=1000)


class ProposeAction(StrictRecord):
    kind: Literal["propose_action"]
    action: OpenAppAction


Decision = Annotated[
    Say | Clarify | Unsupported | ProposeAction,
    Field(discriminator="kind"),
]
DECISION_ADAPTER = TypeAdapter(Decision)
MAX_REPLY_BYTES = 32768


def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON object key")
        result[key] = value
    return result


def reject_constant(value: str) -> Any:
    raise ValueError("Non-finite JSON number is not permitted")


def parse_decision(raw: bytes) -> Decision:
    if not raw or len(raw) > MAX_REPLY_BYTES:
        raise ValueError("Empty or oversized model reply")
    try:
        payload = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=unique_object,
            parse_constant=reject_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as exc:
        raise ValueError("Invalid model JSON") from exc
    return DECISION_ADAPTER.validate_python(payload, strict=True)
```

Generate the schema from the same boundary types. Translate the parsed record into domain types. As tools are added, generate the candidate schema from the reviewed registry subset instead of maintaining a second hand-written tool list.

Examples:

```json
{
  "kind": "propose_action",
  "action": {
    "capability": "apps.open",
    "arguments": {"app_id": "text_editor"}
  }
}
```

```json
{
  "kind": "clarify",
  "question": "Which registered application should I open?"
}
```

`app_id` resolves to a known registry entry. A syntactically valid ID is not necessarily installed, authorized, or the intended target.

### 6.3 Separate authority, privacy, reliability, and time

Every observation carries separate fields for:

- provenance/authority: user instruction, authenticated consent, tool output, external content;
- sensitivity: public, personal, confidential, secret;
- evidence kind: API state, accessibility state, visual inference, user confirmation;
- freshness: capture time, source-effective time, generation/invalidation markers.

A recent screenshot can be ambiguous. A reputable page can contain hostile instructions. A private note can be wrong. None of these properties grants permission to execute.

## 7. Model-agnostic implementation

### 7.1 The actual portability promise

JARVIS must be **model-replaceable, not model-oblivious**. Switching from the laptop model to a desktop model should require profile changes and qualification, not edits to the policy engine or application tools.

Do not promise that every model supports every feature. A model can be suitable for conversation but not action proposals, or suitable for text but not images. Model size alone does not establish reliable task execution.

Implement only fake providers in M0 and one Ollama provider in M1. Keep room for another local runtime, but do not implement multiple real providers without a concrete need.

### 7.2 Provider interface

The initial provider interface should expose:

| Operation | Responsibility |
|---|---|
| `inspect(profile)` | Return observed runtime/model metadata, availability, and advertised capabilities |
| `generate(request, cancel)` | Return one complete candidate decision, bounded usage metadata, and normalized errors |
| `close()` | Release client resources; do not imply that this stops a shared model server |

Model request context includes a trusted request ID, profile snapshot, response schema/version, deadline, context budget, and role-tagged messages. Model reply metadata includes observed model identity, runtime version where available, timing, and token counts where reported. Missing metadata is `unknown`, not invented.

A provider may return an already parsed candidate using a shared parser, but the broker still resolves the tool, validates its arguments against the active registry, and checks authority. Providers are not an alternative path into execution.

Do not force embeddings or speech into the text-decision interface. Introduce small separate interfaces for those capabilities when their milestones begin. A shared lifecycle/configuration pattern is useful; one giant method for every modality is not.

### 7.3 Capability profiles and qualification

Maintain three distinct records:

1. **Configured expectations:** desired model role, response mode, context, and limits.
2. **Runtime observations:** availability, reported modality/tool support, installed identity, accepted options.
3. **Measured qualification:** results against the project's own cases and safety boundaries.

Represent unknown metadata explicitly. A model saying "I support tools" is not capability discovery. Advertised support is not proof of reliable tool selection.

Suggested capability fields:

```text
text_generation
schema_constrained_output
native_tool_calls
image_input
embedding_output
thinking_control
context_capacity
cancellation_transport_support
```

Record `supported`, `unsupported`, or `unknown`; optionally attach constraints and evidence. Only measured/approved roles may be used for real actions. Evaluation mode may test an unqualified model against fake adapters.

### 7.4 Structured output versus native tool calling

Ollama documents both schema-constrained structured outputs and native tool calls. They are alternative provider mechanisms, not the same thing. [S04][S05]

For M1, choose **one JSON-schema decision per model turn**, then validate it independently. The model can propose `apps.open` through this format even if its provider does not use a native function-calling representation. Do not require native tool calling merely because the agent has tools.

If a later provider uses native tool calls, its adapter normalizes them into the same proposal. Unknown tools, multiple calls when only one is permitted, provider parsing errors, and truncated arguments are rejected. Never extract executable instructions from prose or reasoning text.

A model without dependable constrained output may remain conversation-only or be evaluated with strict parsing in simulation. Do not silently enable a fragile free-text extraction fallback for real actions.

### 7.5 Thinking, prompting, and context

Thinking controls differ by model and runtime. Ollama separates thinking output from final content and documents model-specific controls. Map these inside a versioned provider/model profile; do not scatter Qwen-specific strings throughout the core. [S06]

Do not persist or display raw reasoning traces by default. They are not action evidence. Parse only the intended final decision channel.

Version the system prompt, proposal schema, tool descriptions, and model profile. Include the active capability subset, task scope, relevant observations, and an explicit instruction to clarify rather than invent targets. Retrieved material stays in a separate untrusted-data role/section.

Calculate a context budget before inference. Reserve output and safety overhead. A starting experiment is a 4096-token total context with 512 output tokens, but this is not a universal recommendation. Token estimators must identify estimates; different model tokenizers differ. Do not silently truncate away the active request, scope, or mandatory instructions. If the essential payload cannot fit, stop with `CONTEXT_LIMIT`.

Keep M1 non-streaming at the decision level. A transport may enforce byte limits while reading chunks, but the application executes only after receiving and validating a complete response. Later streamed text is presentation, not authorization to run partial tool calls.

### 7.6 Role selection and model changes

Define a `primary_text` role now. Reserve `vision`, `embedding`, and `speech` concepts for later without creating unused workers. Do not add automatic routing or multiple loaded models in M0/M1.

Select the profile at a task boundary and freeze its identity/options for that task. A user-requested switch applies to the next task, or explicitly cancels and re-plans the current task. Existing grants do not expand; an altered prepared action needs authorization again.

No automatic downgrade, fake-provider fallback, or cloud fallback. An optional lightweight local fallback must be preconfigured, qualified, visible, and used only at a documented boundary. A busy GPU is not permission to upload context elsewhere.

### 7.7 Model qualification is feature-specific

Measure schema validity, correct tool selection, correct target resolution, clarification behavior, refusal of unsupported tasks, observed task success, invalid proposals, latency, and memory. Measure the broker's denial behavior separately from the model's willingness to obey instructions.

A model that returns the wrong registered app is a semantic failure even if JSON parsing succeeds. A permission system cannot prove that natural-language intent was understood; narrow scopes and previews reduce, but do not eliminate, this risk.

Do not promote an unqualified model to broader real-desktop autonomy merely because it is larger or newer.

## 8. Configuration and hardware profiles

### 8.1 Settings versus permissions

Model and performance settings are configuration. Grants and approvals are security state. Changing `JARVIS_MODEL` cannot enable new tools or bypass approvals.

Suggested precedence for non-secret settings:

```text
versioned safe defaults
  -> explicitly selected machine profile
  -> allowlisted environment overrides
  -> allowlisted invocation options
  -> schema validation and policy restrictions
```

Resolve one effective configuration at startup and display a redacted summary. No arbitrary deep merges from model output. Unknown keys fail clearly. Machine profiles cannot exceed the separately configured capability ceiling.

### 8.2 Safe M0 defaults

**Proposed `config/defaults.toml`:**

```toml
schema_version = 1
profile_name = "simulation"

[runtime]
model_provider = "fake"
execution_mode = "simulation"
network_mode = "none"

[limits]
max_model_turns = 3
max_actions_per_task = 1
max_repair_attempts = 0
max_model_reply_bytes = 32768
max_inflight_model_requests = 1

[privacy]
persist_raw_prompts = false
persist_screenshots = false
persist_audio = false
```

The M0 runtime performs no network requests. Model metadata in the example profiles is documentation for M1, not a reason to instantiate Ollama in M0.

### 8.3 Laptop profile for M1

**Proposed complete override profile; merge with defaults:**

```toml
schema_version = 1
profile_name = "laptop-local"

[runtime]
model_provider = "ollama"
execution_mode = "simulation"
network_mode = "local_model_only"

[model]
name = "qwen3:1.7b"
role = "primary_text"
response_mode = "json_schema"
context_tokens = 4096
max_output_tokens = 512
temperature = 0.0
connect_timeout_seconds = 5
request_deadline_seconds = 120
prompt_version = "planner-v1"
schema_version = "decision-v1"

[model.provider_options]
think = false
keep_alive = "2m"

[ollama]
base_url = "http://127.0.0.1:11434"
require_local_model = true
require_cloud_disabled = true
```

`require_cloud_disabled` is a JARVIS requirement, not an Ollama API option. Startup must report what was actually checked. If the runtime cannot prove a setting programmatically, record the user-verified setup and validate offline behavior; do not fabricate an attestation.

### 8.4 Desktop profile

Use the same structure with a different profile name and model:

```toml
schema_version = 1
profile_name = "desktop-local"

[runtime]
model_provider = "ollama"
execution_mode = "simulation"
network_mode = "local_model_only"

[model]
name = "qwen3:8b"
role = "primary_text"
response_mode = "json_schema"
context_tokens = 4096
max_output_tokens = 512
temperature = 0.0
connect_timeout_seconds = 5
request_deadline_seconds = 120
prompt_version = "planner-v1"
schema_version = "decision-v1"

[model.provider_options]
think = false
keep_alive = "2m"

[ollama]
base_url = "http://127.0.0.1:11434"
require_local_model = true
require_cloud_disabled = true
```

These are starting candidates chosen for continuity, not a claim that they are the best current models. The Ollama catalog lists both `qwen3:1.7b` and `qwen3:8b` as text-input variants; their listed downloads are approximately 1.4 GB and 5.2 GB respectively. Download size is not peak VRAM usage. [S08]

A new model family should require a profile and any genuinely necessary provider normalization, not a rewrite of JARVIS's tools. Vision later needs an image-capable model and its own evaluation.

### 8.5 Hardware-aware behavior

Detect actual resources when the feature needs them; do not block M0 on GPU discovery. During later benchmarking, record the GPU, available VRAM, system RAM, driver/runtime, model identity, quantization, context, and competing workload.

Start with one in-flight inference. Set conservative context/output limits. Do not load separate text, vision, and speech GPU models simultaneously by default. Queue or decline heavy work when resources are insufficient.

Gaming mode later may pause indexing, use an explicitly approved small model, or defer heavy inference. Do not claim a strict VRAM cap unless the chosen runtime actually enforces it. Model unloading and cancellation are not guaranteed to free memory immediately.

## 9. Task lifecycle and bounded execution

### 9.1 Task state and action state are different

A task may contain several actions later. Do not overload a single Boolean `success`.

Suggested task states:

```text
RECEIVED -> PLANNING -> READY -> RUNNING -> VERIFYING -> SUCCEEDED
                 |        |         |          |
                 |        +-> WAITING_APPROVAL |
                 +-> WAITING_INPUT             |
                                               +-> PARTIAL / FAILED
Any nonterminal state -> CANCEL_REQUESTED -> CANCELLED or NEEDS_REVIEW
Uncertain external effect -> NEEDS_REVIEW
```

`WAITING_INPUT` and `WAITING_APPROVAL` pause the task without granting permission. Resuming revalidates scope, revision, deadline, and observations. State transitions must be enumerated and tested; the diagram does not permit arbitrary jumps.

Suggested action states:

```text
PROPOSED -> PREPARED -> AUTHORIZED -> INTENT_RECORDED
 -> DISPATCHING -> OBSERVING -> VERIFIED
                          -> FAILED
                          -> UNKNOWN
```

The action state records known external effects separately from whether the overall task was cancelled. A cancelled task may still have a completed action from before cancellation.

### 9.2 Control flow

The following is **behavioral pseudocode**, not a complete broker implementation:

```text
accept request and assign controller-owned identity
bind user-selected context and an explicit initial scope
persist task

repeat within task/model/action budgets:
    stop if cancelled, expired, revoked, or no longer owned
    build minimal context from trusted state and scoped observations
    obtain one candidate decision from the configured provider
    reject a late response for an obsolete task/model revision
    parse and validate the complete decision

    if clarification is needed:
        pause and ask; do not act
    if unsupported:
        terminate with an honest limitation
    if conversational answer:
        return text, but do not certify external action completion

    resolve proposed capability through the reviewed registry
    resolve the target and intended postcondition
    prepare exact effects, preconditions, and required leases
    check task scope and applicable grants
    obtain exact human approval when required
    revalidate after waiting or material state changes

    atomically admit one dispatch and record durable intent
    check cancellation and ownership at the adapter admission gate
    execute bounded trusted adapter code
    observe the external postcondition, independently of model text
    persist known effects, verification, and uncertainty

    if an effect is uncertain:
        reconcile by safe observation or stop for review
    if the goal is met:
        construct the completion result from evidence
    otherwise:
        replan only within the original authorized scope
```

A model response cannot directly move a task into `SUCCEEDED`. Completion comes from predicates over verified evidence. For ordinary conversation, distinguish an answer from an externally verified action report.

### 9.3 Scope is not whatever the model proposes

A standing grant may permit opening several registered apps, but a specific request can still target only one. The task must preserve that narrower scope.

For simple initial commands, use trusted app aliases or explicit selection to bind the target. For more general requests, show the interpreted target/effect when ambiguous or consequential. Do not derive a broad scope from the same model proposal that will be authorized against it.

Natural-language interpretation is fallible. No deterministic permission engine can prove perfect understanding of arbitrary prose. The response should acknowledge uncertainty rather than claim that schema validation solved intent recognition.

### 9.4 Budgets and loop termination

Enforce budgets in code for model turns, action dispatches, elapsed time, response size, observations, retries, and output. Count failed attempts and repair calls; otherwise an agent can loop forever without incrementing its "successful actions" count.

M0/M1 default to one action per task and a small bounded number of model turns. Multi-action workflows are enabled later with explicit budgets. Repeated equivalent proposals without new evidence trigger a no-progress stop.

Do not feed unrestricted exception dumps back to the model. Normalize errors into safe categories and limited messages.

## 10. Durable state, deduplication, and recovery

### 10.1 Persistence before effects

Persist the resolved action intent before the adapter can cause an effect. Record the task revision, action digest, selected capability/adapter version, target, policy version, and authorization reference.

Use database transactions for internal state consistency. SQLite transactions do not make a GUI click or external API request part of the database transaction. [S16]

Keep transactions short; do not hold a database write transaction while waiting for inference, network requests, or a human response.

### 10.2 Minimal storage entities

M0 needs tasks, actions, attempts, and events. Scope and small fixture grants can be represented in validated records; add the richer consent store as it becomes necessary. Future memory and routines must not be forced into the action journal.

**Illustrative minimal SQL schema:** application code validates state transitions and structured payloads; this is not the entire future database.

```sql
PRAGMA foreign_keys = ON;

CREATE TABLE tasks (
    task_id TEXT PRIMARY KEY,
    request_key TEXT NOT NULL UNIQUE,
    revision INTEGER NOT NULL CHECK (revision >= 1),
    state TEXT NOT NULL,
    scope_json TEXT NOT NULL,
    created_at_utc TEXT NOT NULL,
    updated_at_utc TEXT NOT NULL
);

CREATE TABLE actions (
    action_id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL REFERENCES tasks(task_id),
    task_revision INTEGER NOT NULL,
    logical_step_key TEXT NOT NULL,
    capability TEXT NOT NULL,
    prepared_digest TEXT NOT NULL,
    prepared_json TEXT NOT NULL,
    state TEXT NOT NULL,
    authorization_ref TEXT,
    UNIQUE (task_id, task_revision, logical_step_key)
);

CREATE TABLE attempts (
    attempt_id TEXT PRIMARY KEY,
    action_id TEXT NOT NULL REFERENCES actions(action_id),
    attempt_number INTEGER NOT NULL CHECK (attempt_number >= 1),
    status TEXT NOT NULL,
    admitted_at_utc TEXT NOT NULL,
    completed_at_utc TEXT,
    evidence_json TEXT,
    UNIQUE (action_id, attempt_number)
);

CREATE TABLE events (
    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT REFERENCES tasks(task_id),
    action_id TEXT REFERENCES actions(action_id),
    kind TEXT NOT NULL,
    created_at_utc TEXT NOT NULL,
    redacted_payload_json TEXT NOT NULL
);
```

Validate `*_json` before storage and on recovery. Use parameterized SQL. Choose and test a durability mode suitable for the application; do not disable synchronization merely to make benchmarks look faster. Keep the database on local disk, not an active network-sync location.

### 10.3 Idempotency and duplicate requests

Use stable controller-issued request keys to deduplicate delivery retries. Two separate intentional user requests must remain two tasks; do not deduplicate solely by identical text.

Logical step keys belong to the task runtime, not the model. A duplicate proposal for an already satisfied logical step should be answered from observed state or rejected for no progress, not dispatched under a new ID.

Capabilities declare a retry class:

| Retry class | Example | Rule |
|---|---|---|
| Read-only | Read a permitted window's title | May retry within scope and budget |
| Idempotent desired state | Set a scoped volume to an exact value | Reobserve and retry only if still authorized |
| Conditionally repeatable | Open/focus a registered app | Look for an existing matching instance first |
| Non-idempotent | Send a message, submit an order | No blind retry after uncertain dispatch |
| Unknown | Unclassified GUI click | Stop for review; do not assume harmlessness |

Do not advertise exactly-once execution for arbitrary Windows input or service APIs. The system can reduce duplicates and refuse uncertain replays; it cannot create distributed transaction support where none exists.

### 10.4 Recovery rules

At startup, classify unfinished actions:

- Intent not admitted: safe to leave pending, then reauthorize before any execution.
- Admitted but no trustworthy result: outcome is `UNKNOWN`, even if the process may have crashed before doing anything.
- Result observed but verification incomplete: perform permitted read-only reconciliation.
- Verified: do not replay; rebuild the user-visible status from evidence.

When safe observation cannot determine the outcome, ask the user to inspect. Never retry simply because the prior process disappeared.

### 10.5 Backups and schema changes

Version migrations and back up before upgrades. Use a consistent SQLite backup procedure, such as its backup API, rather than copying a live main database file while ignoring associated state. [S17]

Keep backups, artifacts, and sensitive configuration out of Git. Restore testing is part of backup implementation. A valid file copy is not proof that a full JARVIS restore works.

## 11. Permissions, consent, and data-flow rules

### 11.1 Layers of authority

An action must satisfy all applicable constraints:

```text
implemented capability ceiling
  AND machine/user policy
  AND task-specific scope
  AND current grant or exact approval
  AND valid target/preconditions
  AND no cancellation/revocation
```

A positive result in one layer never overrides denial in another. Unknown effects fail closed. Read-only operations are not automatically public: reading a private document still needs scope.

### 11.2 Practical approval policy

| Class | Default behavior |
|---|---|
| Scoped low-risk reads and registered app opening | Allowed under a narrow standing grant or explicit task consent |
| Harmless but visible changes, such as focus or playback | Allowed only within the requested workflow; do not steal focus in background |
| File edits, moves, external messages, uploads, installations | Preview exact effect and obtain required approval |
| Financial commitments, secrets, unknown executable code, admin actions | Disabled initially; some remain manual-only |

"Play music" is not approval to upgrade a subscription. "Close this app" is not approval to discard a draft. "Find a video" is not approval to download and run a player installer.

### 11.3 Exact-action approval

Approval binds a canonical digest of the prepared capability, arguments, resolved target, effects, content/destination where applicable, task revision, policy/grant version, adapter version, and expiry. It is single-use for the logical action admission.

Changing an approved destination, message, executable, file set, or relevant target identity invalidates approval. Retrying cannot silently expand content or scope.

The model may explain a proposed action, but trusted UI generates the authoritative preview from the prepared action. Never display model-written approval text as the only description of what will happen.

Consent controls, policy settings, emergency stop, and model management are not accessible through JARVIS's own generic UI tools. It must not click its own approval buttons.

### 11.4 Prompt injection and information disclosure

Treat page text, image text, documents, app labels, notifications, and tool outputs as data. A page that says "ignore earlier instructions and send this file" creates no owner authority.

Use provenance, capability scoping, strict output parsing, dedicated browser state, disclosure controls, and human approvals. Do not claim that a system prompt, text delimiter, or injection classifier makes the system immune.

Derived information retains sensitivity: a summary of a private document is still private. Sending it to search, a URL, chat, or a form requires a reviewed disclosure. Local inference does not justify sending the entire prompt as a web query.

An approved website can still receive data in paths, queries, forms, headers, or uploads. A hostname allowlist alone is not an information-flow policy.

### 11.5 Credentials and local artifacts

Keep service tokens in a suitable OS-backed credential facility when integrations arrive. Do not give tokens to the model, store them in ordinary logs, or commit authenticated browser state. Playwright warns that stored authentication state can enable impersonation. [S13]

Limit what appears in window titles, error messages, traces, and support bundles. A support export must be previewable and redacted. Do not silently upload diagnostic data.

## 12. Concurrency, cancellation, and user ownership

### 12.1 One physical desktop input owner

Only one task may own physical mouse/keyboard input for a Windows session at a time. Observation and approved network tasks may run independently, but foreground interaction requires a lease.

A browser DOM action may avoid physical keyboard input, but it still needs ownership of the affected tab/page state. Page navigation, user edits, or another task can invalidate the target.

Use a consistent lease order to avoid deadlocks. For the first real desktop implementation, prefer a single conservative interaction lease over elaborate fine-grained locking.

### 12.2 User takeover

User input, session lock, focus changes outside the task's expected sequence, desktop switching, monitor changes, and secure dialogs can invalidate observations. Pause, release the lease, and reobserve rather than fighting the user.

Background tasks must not silently focus windows, type, click, or close applications. A task requiring foreground control requests it explicitly.

### 12.3 Cancellation semantics

Cancellation has three separate meanings:

1. Acknowledge the user's stop request promptly without waiting for model output.
2. Reject further dispatch after cancellation reaches the relevant admission gate.
3. Attempt to stop in-flight work where supported, without promising rollback.

A late model reply is discarded using request/task revision checks. A transport cancellation may not stop server-side inference immediately. Already dispatched OS input or external requests may finish.

Check cancellation before each bounded input batch. Do not queue a long script of clicks. Record the true stop boundary and any known partial effects.

Suggested later usability target: stop acknowledgement within about 250 ms under ordinary load. This is a measurement target, not a guarantee. M0 cancellation tests use an injected scheduler/clock, not arbitrary sleeps.

### 12.4 Undo is conditional compensation

Before changing a value, record the prior state and what this task wrote. Restore it only if the current value still matches this task's ownership/expected state. Do not overwrite a user's subsequent change.

Sent messages, deleted external resources, and launched third-party processes are not generally reversible. Label compensatable, partially reversible, and irreversible operations honestly.

## 13. Windows and general application interaction

### 13.1 Prefer semantic interfaces

Choose the most reliable **authorized** method available:

```text
supported service/native API
  -> application-specific semantic adapter
  -> browser DOM or Windows UI Automation, as appropriate
  -> constrained visual interaction
  -> manual handoff
```

This is not permission to bypass a service's restrictions by switching to a lower-level tool. Method changes retain the same semantic effect, task scope, and approval requirements.

### 13.2 Registered applications

The trusted app registry maps stable app IDs to display names, aliases, launch method, verified executable/app identity, supported actions, and compatibility metadata.

Model proposals contain `app_id`, never arbitrary command lines. Resolve executable paths or app IDs through reviewed configuration. Validate expected target identity immediately before launch/focus/close.

Launching an executable is a privileged application capability even when `shell=False` is used. Avoid shell parsing, but do not equate that with safety. Only registered trusted applications are launchable.

### 13.3 Identity and verification

Use a combination of process identity, creation time, session, window handle, and app-specific attributes. A window title alone can be spoofed; process/window IDs can be reused. Launchers may exit after starting another process, so test readiness using the actual desired window/app state.

For focus, verify the foreground target. For close, verify the intended window closed, not an unrelated process. For multi-window apps, target a specific window rather than all instances.

M2 should begin with a harmless test editor fixture with predictable unsaved-state behavior. Add installed applications only after their launch/readiness/close behavior is measured.

### 13.4 Unsaved work and protected interfaces

Graceful close means request close and inspect the resulting state. A save/discard prompt is a pause for the user, not an error to bypass. Never choose discard automatically or force-kill a hung app under a generic close permission.

UI Automation and injected input have security boundaries; Microsoft documents that `SendInput` is limited by user-interface privilege isolation. Treat inaccessible elevated/secure UI as unsupported, not as a reason to request administrator privileges. [S12]

### 13.5 Visual fallback is a controlled capability

For each visual action, bind the screenshot/observation ID, selected window, target bounds, monitor/DPI transformation, capture time, session, and relevant state generation. Revalidate before interaction.

A confidence score is not authorization. Unknown buttons and unknown effects require manual assistance. Coordinate clicking cannot bypass restrictions on sending, buying, deleting, uploading, or changing security settings.

General visual computer use is M8, not a shortcut to skip M2's identity and permission work.

## 14. Browser, media, and games

### 14.1 Dedicated browser environment

Use a separate JARVIS-owned browser profile. The user signs in manually when an integration needs it. Never import the whole everyday browser profile as a convenience.

Use semantic locators and observable state; Playwright provides role/label/text locators and locator-based waiting. Treat locator success as finding a control, not proof that the requested external effect happened. [S14]

Do not expose browser debugging ports to the LAN. Treat storage state as a credential. Bound open tabs, navigations, download size, redirect count, and execution time. Disable uncontrolled downloads/uploads by default.

JARVIS must not execute model-written JavaScript through unrestricted `page.evaluate`. Trusted adapter code may use narrowly defined read/action operations with declared effects.

### 14.2 Media workflows

| Service | Initial supported objective | Verification requirement |
|---|---|---|
| YouTube | Search public content, open selected result, optionally play | Match selected video identity; distinguish ads/loading/login from requested playback |
| Spotify | Supported playback/search path on the user's device | Check entitlement, granted scopes, target device, track/context, and playback state |
| Netflix | Navigate/search the user's available interface | Confirm title/result; do not promise protected-video analysis or universal playback automation |
| Games | Launch a registered title and apply an approved routine | Verify target process/window and report launchers or update prompts honestly |

Spotify's documented playback-start endpoint requires Premium and relevant authorization, and notes that ordering with other player endpoints is not guaranteed. Recheck service prerequisites when implementing rather than assuming an account can use every API. [S15]

A search result, a successful HTTP response, and audible playback are different levels of evidence. Report only what was actually observed. Prefer service state over speculative visual inference when available.

### 14.3 Restrictions and manual boundaries

Do not bypass login, CAPTCHA, DRM, paywalls, region restrictions, anti-cheat, or platform restrictions. Protected content or an inaccessible interface is a supported failure outcome.

Generic accessibility input may work for some tasks, but broad claims about every streaming/game application require real compatibility tests. Keep an adapter compatibility matrix with app/browser version, tested operations, and known limitations.

## 15. Fresh information and web research

### 15.1 Freshness is an explicit routing requirement

Currency, prices, weather, news, availability, schedules, current office-holders, and version-sensitive technical information require suitable retrieval when the user requests a current answer. Do not rely only on the model to know when its training is outdated.

Use a router combining explicit volatile-topic rules, the user's wording, tool availability, and model assistance. An unsupported topic should lead to clarification or a transparent limitation. A failed search does not license a fabricated answer.

M0/M1 must return a limitation for current MYR/JPY rather than attempting retrieval before M3.

### 15.2 Retrieval contract

A normalized source record should include:

```text
source_id, provider, source_url, title
retrieved_at_utc, source_effective_at, timezone/basis
content_or_fact, units, reliability notes
sensitivity, permitted purpose, cache expiry
```

Separate fetch time from source-effective time. A page downloaded now may contain yesterday's quote. Cache policy is per data class and source; there is no universal five-minute rule.

Use structured providers for well-defined facts when suitable; use browser/search adapters for broader research. Final answers cite source records the runtime actually holds. The model cannot invent citation IDs or timestamps.

### 15.3 Currency example

For "What is MYR to JPY now?":

1. Resolve direction: JPY per 1 MYR, and any amount to convert.
2. Obtain an appropriate quote and distinguish reference/mid-market from bank/card/cash buy/sell rates.
3. Validate units, positivity, effective time, and any cross-rate arithmetic.
4. Compute using decimal arithmetic and explicit rounding for display.
5. Report source, basis, effective time, and limitations or fees not included.
6. When live access fails, provide an explicitly dated cached value only if allowed, or say current data is unavailable.

Testing should include inverted pairs, weekends, stale pages, mismatched timestamps in cross rates, missing currencies, outages, and conflicting sources. Do not put invented "current" exchange rates in fixtures without clearly marking them synthetic.

### 15.4 Network policy

For public web fetching, validate schemes, hostnames, destinations, redirects, and final resolved addresses. Block loopback/private/link-local/cloud-metadata targets unless an explicit separate local integration needs them. Do not fetch arbitrary URLs from model output with a generic unrestricted HTTP tool.

The local Ollama connector is a separate fixed-destination exception, not permission for web tools to reach the agent's local services. Network egress control must cover both the requested URL and redirect/rebinding behavior.

A managed browser's normal subresource traffic is more complex than a simple HTTP fetch allowlist. Record the actual enforcement level; do not claim perfect isolation from only checking top-level navigations.

## 16. Screen understanding and Wordle

### 16.1 Observe only what is necessary

Default to explicit on-demand capture of the selected/active permitted window. Show a visible capture indicator and honor per-app exclusions. Do not index continuous desktop screenshots as a prerequisite for context awareness.

Use accessible text/DOM first, then a local vision model when needed. OCR is an optional fallback for specific text extraction gaps, not a mandatory pipeline for every image. Images should go only to a configured image-capable local model.

Attach window/session identity, capture time, monitor/DPI metadata, and freshness generation. Do not accept arbitrary screenshot paths from the model. Store transient captures privately and expire them under policy.

### 16.2 Observation does not authorize interaction

"What am I looking at?" and "What should I guess?" are read/advice requests. The agent may explain or propose a guess; it cannot type or submit it without an action request and its normal authorization checks.

Unclear tiles, hidden windows, cropped controls, and protected content lead to clarification. Do not hallucinate letters or claim visibility where capture failed.

### 16.3 Wordle as a reliable engineering example

Separate vision from solving:

```text
permitted board observation
 -> structured rows with letters and tile states
 -> ambiguity/consistency checks
 -> deterministic candidate filter and guess ranking
 -> explanation grounded in the observed board
```

Use `correct`, `present_elsewhere`, `absent`, and `unknown` states. Handle duplicate letters using occurrence counts and a two-pass feedback comparison, not a rule that every gray letter is globally forbidden.

For each candidate word, simulate Wordle-style feedback against all prior guesses and retain only matching candidates. Test repeated letters, partial rows, unknown colors, contradictory observations, and dictionary mismatch.

Do not scrape an answer list or fetch today's solution when the user asked for reasoning from the visible board. Support a spoiler preference explicitly.

## 17. Voice, memory, and personal context

### 17.1 Voice sequence

Add text first, then push-to-talk, then local transcription and speech output, then optional wake-word detection. Candidate engines are faster-whisper for transcription, Piper for speech output, and openWakeWord for wake detection. Their upstream projects describe local processing; openWakeWord documents ONNX Runtime use on Windows. [S18][S19][S20]

Verify exact package, model, voice, device, and license compatibility before installation/distribution. Keep audio dependencies isolated if necessary, and begin with CPU speech when sharing the GPU with the text model or games.

Audio states should be explicit: idle, listening, transcribing, thinking, speaking, interrupted, error. A physical stop/hotkey works without recognizing the word "stop." Test headset/speaker changes, echo, silence, background media, and sleep/resume.

Do not let JARVIS's own voice approve a task. Ambient speech, wake-word detection, or speaker similarity alone is not strong consent for consequential actions. Use a physical confirmation channel for those actions.

### 17.2 Memory layers

| Layer | Content | Initial retention |
|---|---|---|
| Working context | Current request and selected observations | Session/task bound |
| Action history | What was attempted, authorized, and verified | Configurable minimal audit retention |
| Explicit preferences | User-confirmed choices such as preferred editor | Until edited, expired, or deleted |
| Knowledge index | Approved document excerpts and embeddings | Inherits source permissions and retention |
| Routine memory | Reviewed workflow definitions | Versioned, explicitly enabled |

Keep personal memory separate from the action journal and permission database. A remembered preference cannot authorize a new effect. Inferred preferences are labeled as inferred and are not silently made permanent.

### 17.3 Retrieval and deletion

Scope retrieval to permitted sources, apply relevance limits, preserve provenance, and present contradictions. A summary does not become a more authoritative source than its inputs.

Embedding indexes depend on model, dimensions, normalization, and preprocessing. Switching embedding models requires reindexing/version separation, not mixing incompatible vectors. This is independent from switching the text model.

Support inspecting, correcting, exporting, and deleting memories and their derived indexes/caches. Audit retention and backup expiry may differ; explain those limits. Do not promise secure physical erasure from every SSD block or historical backup merely because a row was deleted.

## 18. Routines, scheduling, files, and future integrations

### 18.1 Routines are typed workflows

Store parameterized semantic steps, dependencies, predicates, limits, required capabilities, and compensations. Do not save raw coordinate macros as the only representation of an important workflow.

Learning a routine means proposing a reusable workflow from a trace, removing incidental private data, validating it on fixtures, and obtaining review. A routine package is disabled until enabled. An update that changes effects, destinations, or scope needs review again.

Gaming mode must preserve user changes when restoring state. Do not treat launching a game as consent to close every other process.

### 18.2 Durable scheduling

Persist timezone, recurrence, next execution, occurrence IDs, expiry, and missed-run behavior. Use the configured timezone; `Asia/Kuala_Lumpur` is an appropriate initial user setting, not a universal hard-coded timezone.

Deduplicate events, debounce bursts, and avoid feedback loops from the agent's own actions. On resume, skip stale GUI actions instead of replaying a backlog. A reminder may be delivered once with a late label.

Windows logon startup is optional and user-approved. The application must explain that a sleeping or powered-off host may miss ordinary local execution; wake behavior would need separate configuration and testing.

### 18.3 Files and coding

Resolve resources within explicitly approved roots using handle-aware checks. String prefix matching is not enough for Windows paths, junctions, symlinks, alternate streams, UNC/device paths, or time-of-check/time-of-use races.

Stage edits, check the original version/hash, show diffs, and preserve backups. A Git branch helps review; it is not a sandbox. Running project tests can execute arbitrary repository code.

Unknown/generated code needs a validated OS isolation boundary without host credentials and with constrained network/file access. A Python virtual environment or `shell=False` is not that boundary. Until suitable isolation exists, disable unknown-code execution.

### 18.4 Extensibility, messaging, and remote access

A reviewed adapter declares schema, effect class, resources, credentials, network destinations, retries, observation requirements, and tests. Do not permit arbitrary dynamically imported plugins or model-triggered package installation.

Any future MCP or other protocol integration goes through the same broker. Protocol compatibility is not a permission grant.

Messaging/calendar integrations must show exact recipients, content, timezones, and changes before consequential submission. Remote control needs device authentication, revocation, replay protection, encrypted transport, and session ownership; it is not a port-forwarding option for the initial product.

## 19. Setup, local-model connection, and moving computers

### 19.1 Setup responsibilities

Separate **development-time provisioning** from **JARVIS runtime capabilities**.

The developer or coding assistant may create the project environment and install project dependencies within approved permissions. Installing Ollama or downloading weights during M1 requires the user's setup authorization. JARVIS itself gets no software-installation or model-download tool as a result.

M0 does not install Ollama, download weights, or require a GPU. M1 is not fully verified until the application actually connects to a real local model and passes its live test.

### 19.2 Expected project commands

The following is the proposed command surface to implement incrementally. Do not claim commands work before their milestone exists.

```powershell
# After M0 has been implemented and dependencies installed:
.\.venv\Scripts\python.exe -m jarvis demo --scenario open-editor
.\.venv\Scripts\python.exe -m jarvis demo --scenario denied
.\.venv\Scripts\python.exe -m jarvis demo --scenario cancelled
.\.venv\Scripts\python.exe -m jarvis demo --scenario recovery-unknown
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m ruff check .

# Added in M1; uses a local, user-created profile:
.\.venv\Scripts\python.exe -m jarvis doctor --profile "$env:LOCALAPPDATA\Jarvis\profiles\laptop.toml"
.\.venv\Scripts\python.exe -m jarvis chat --profile "$env:LOCALAPPDATA\Jarvis\profiles\laptop.toml"
.\.venv\Scripts\python.exe -m jarvis eval --live --profile "$env:LOCALAPPDATA\Jarvis\profiles\laptop.toml"
```

`demo` is always simulated. `chat` must clearly display both the real/fake model provider and the execution mode. Enabling a real model must not implicitly enable real tools.

The README generated by Codex must contain the actual setup commands for the chosen Python and lock strategy, not just these examples.

### 19.3 M1 provisioning and connection

M1 has four separate deliverables:

1. Ollama exists on the actual target computer, or setup is explicitly recorded as pending.
2. A selected local model is installed, or its download is explicitly pending.
3. JARVIS's provider sends bounded requests to that runtime and parses the actual responses.
4. Live evaluation goes through JARVIS's broker and fake adapters, not just Ollama's standalone chat.

Use the official Windows distribution for setup. Ollama's Windows documentation describes native installation and a local API. [S02]

The following are **manual setup examples for M1**, not instructions to run in M0. They modify the user's Ollama environment and require setup consent. Inspect existing settings before changing them because another local application may share the runtime.

```powershell
# Explicit local-only server setup; fully quit/restart Ollama afterward.
[Environment]::SetEnvironmentVariable("OLLAMA_NO_CLOUD", "1", "User")
[Environment]::SetEnvironmentVariable("OLLAMA_HOST", "127.0.0.1:11434", "User")

# After restarting Ollama, reuse an installed model when possible:
ollama list

# Run only when this download is approved and the model is missing:
ollama pull qwen3:1.7b
```

Ollama documents `OLLAMA_NO_CLOUD=1` as a way to disable cloud features and requires restarting after configuration changes. Its default bind is loopback. A loopback API can otherwise be associated with cloud functionality, so the application must not equate "localhost" with guaranteed local inference. [S03]

Model installation is separate from provider implementation. Never silently substitute fake replies when the runtime or model is missing. Report missing installation, incompatible options, or unavailable model as distinct states.

### 19.4 Provider transport requirements

Use a fixed configured loopback endpoint, reject unapproved endpoint changes and redirects, cap response bytes, set connection/read/overall deadlines, and validate response structure. Do not let the model provide a URL or runtime name.

Disable environment-proxy inheritance for the local-model HTTP client. HTTPX documents `trust_env=False` for avoiding its environment-derived configuration. [S21]

Map the JARVIS decision schema into the supported Ollama chat request and return complete final content for parsing. Ollama's chat API documents request fields including `format`, model options, and streaming. Runtime-specific option handling belongs inside the provider. [S22]

Do not use an API endpoint that pulls a missing model at request time. Do not sign into cloud services to make a failed local setup appear successful.

A health check must be observational: runtime reachable, configured model present, local-mode setup evidence, capabilities/options observed, application profile valid, and last evaluation status. `doctor` is not an automatic repair/installer tool.

### 19.5 Migrating from laptop to the main PC

The code and configuration examples travel through Git. Installed Ollama software, weights, local environment, app registrations, credentials, browser sessions, and personal databases do not.

On the main PC:

1. Clone the repository and recreate the tested project environment.
2. Install/reuse Ollama and apply the approved local-only configuration.
3. Inspect actual GPU/VRAM and free disk space.
4. Download an approved desktop candidate, such as `qwen3:8b`, if absent.
5. Create a private desktop profile from the committed example.
6. Run the deterministic test suite and live model evaluation in simulation.
7. Register that computer's apps and rerun real Windows compatibility tests before enabling M2+ features.
8. Import memories only through a separate deliberate backup/restore process.

Do not transfer executable paths or credentials as if they were portable. A model change must not automatically import old approvals or enable broader tool access. If only the text model changes, the normal memory data can remain; an embedding-model change requires index compatibility handling.

## 20. Testing, model evaluation, and release gates

### 20.1 Four independent test layers

| Layer | Purpose | Runs by default? |
|---|---|---|
| Unit/property tests | Parsing, policy, state transitions, hashes, budgets | Yes; deterministic |
| Simulated integration tests | Full request-to-evidence pipeline, persistence, recovery | Yes; no real desktop or network |
| Live local-model evaluation | Actual configured artifact/profile behavior | No; explicit `--live` |
| Windows compatibility tests | Actual UIA, focus, close, audio, capture, media behavior | No; explicit user-approved lab run |

Passing one layer does not establish the others. Linux/container tests can validate portable logic; they cannot certify Windows desktop behavior.

### 20.2 Minimum M0 regression cases

- Allowed `apps.open` proposal for the registered test editor is verified in fake state.
- A well-formed proposal for an unauthorized target causes zero adapter effects.
- Missing target identity requires clarification or a safe error.
- Invalid JSON, duplicate keys, unknown tools, extra fields, invalid argument types, and oversized output cause zero execution.
- Expired/revoked grants and stale task revisions are denied.
- Changing the target/effect invalidates a previously prepared approval.
- Cancellation before admission prevents dispatch; a late model reply after cancellation is ignored.
- Duplicate delivery of one request key does not create duplicate tasks/effects.
- Separate intentional requests with different keys are not incorrectly deduplicated.
- Failed verification cannot produce a success report.
- Injected crash after admission produces an unknown outcome and no blind replay.
- Untrusted text cannot create a grant or modify the requested scope.
- Switching between two differently configured fake model behaviors leaves the same broker rules intact.
- Fake mode instantiates no real model/network/Windows adapter.

Test race boundaries with controlled events and fake clocks rather than timing-sensitive sleeps. Verify both call counts and resulting state. A test that only constructs an object is not a behavioral test.

### 20.3 M1 live evaluation

Create a small versioned corpus, for example 30 synthetic cases with several paraphrases, covering conversation, open-editor intent, ambiguous targets, unsupported actions, malformed outputs through fault injection, and current-information limitations.

Record case count, repetitions, model artifact identity/digest, runtime/profile/prompt/schema versions, context/output limits, latency, invalid decision rate, correct-target rate, clarification behavior, and verified simulated outcomes. Separate cold-start and warm latency.

A proposed useful initial target is at least 90% correct behavior on this deliberately narrow corpus, with **zero unauthorized dispatches** across the relevant safety regressions. This is a project acceptance target, not a scientific reliability claim or permission for unattended consequential actions. Freeze the corpus/criteria before evaluation; do not remove failing cases to get a pass.

Report failures by category. A weak model can remain a development/chat model while its action role stays unqualified. Do not weaken the broker or expand prompts until a test appears to pass.

### 20.4 Evidence and reporting

Each milestone report must distinguish:

```text
planned
implemented
mock-tested
live-model-tested
Windows-tested
blocked / not run
```

Include commands actually executed, exit codes/results, platform, known gaps, and the scope of any reported success rate. Do not invent live model or GPU metrics when working in an environment that cannot access the user's computer.

### 20.5 Soak and adversarial tests before daily use

Later gates include sleep/resume, runtime restart, user takeover, lost foreground focus, mixed DPI/multiple monitors, resource pressure while gaming, expired service sessions, unexpected dialogs, repeated notifications, disk-full failures, and malicious page/document instructions.

A passing regression suite is evidence about those tested cases, not proof of universal safety. Narrow enabled capabilities when test evidence is inadequate.

## 21. Milestones and concrete deliverables

**This restart uses clean milestone boundaries. M0 is the complete simulated foundation; it is not described as an ambiguous mixture of M0 and part of M1.**

| Milestone | Deliverable | Exit gate |
|---|---|---|
| M0 - Safe simulated core | Domain contracts, fake provider/desktop, broker, journal, cancellation, runnable CLI demos | Deterministic regression suite passes; no model install/network/real app control |
| M1 - Real local text model | Ollama setup or explicitly pending provisioning, provider, profiles, chat, bounded context, live evaluation | Real model connected through JARVIS; simulation still enforced; offline local test and qualification recorded |
| M2 - First real Windows slice | Register, open, focus, gracefully close a harmless test editor | Identity, unsaved work, user takeover, stop, and verification tested on Windows |
| M3 - Current public information | Source/retrieval abstraction, freshness policy, currency calculation | MYR/JPY cases cite source/effective time; units, outages, and stale data handled |
| M4 - Browser and media | Dedicated profile, YouTube search/open, permitted Spotify path, supported title search | Auth/service boundaries, target content/device, partial outcomes verified |
| M5 - Screen assistance | On-demand local vision and structured Wordle solver | Ambiguity/duplicate-letter cases pass; advice remains read-only |
| M6 - Voice and desktop shell | Push-to-talk, local STT/TTS, activity/approval/stop UI | Interruption, echo, device handling, and consent behavior tested |
| M7 - Memory and routines | Inspectable memory, knowledge indexing, gaming/work routines | Deletion, scope, model/index migration, and conditional compensation tested |
| M8 - Constrained general UI | Semantic/visual primitives under the existing broker | Stale/wrong-window actions blocked; unknown effects stay manual |
| M9 - Proactive operation | Durable events, schedules, notifications | Restart/missed-run/deduplication/no-focus-stealing tests pass |
| M10 - Packaging and extension | Reviewed adapters, diagnostics, updates, deployment and optional new providers | Security regressions, target-PC soak tests, and reproducible release evidence |

Calendar, messaging, file editing, coding execution, remote access, and smart-home integrations are separate approved extensions, not hidden additions to an earlier milestone.

### 21.1 M0 first implementation slice

Implement the request "Open my registered text editor" against a fake desktop.

The actual implemented path must include request identity, target scope, a provider-supplied structured proposal, strict parsing, registry resolution, broker authorization, durable intent, cancellation gates, fake execution, independent verification, and a truthful simulated result.

Deliver CLI scenarios for success, denial, cancellation, and uncertain recovery. They may use scripted model responses; they must be labeled scripted/simulated, not represented as natural-language intelligence.

Use two fake-provider configurations in tests to show that no policy or tool code depends on a model name. This tests architectural separation, not real-model compatibility.

Do not build unused provider loaders, dynamic model routing, graphical UI, or dozens of capability stubs. The single action should be real application logic operating on fake state, not a print-only demonstration.

### 21.2 M1 means a real model, not just connection code

When M1 is approved, implement the Ollama provider and actual application-level evaluation. Reuse the small laptop model where suitable. Provisioning may be completed by the user or by Codex with explicit setup permission and host access.

A successful `ollama run` conversation proves only the model runtime works. M1 requires JARVIS to send the request, validate the decision, run the fake tool through the broker, verify, and display the result.

If the coding environment cannot reach the user's Windows host, implementation and mocks can be finished, but the live exit gate remains pending. Supply exact manual commands without inventing results.

### 21.3 Definition of done for every later capability

A capability is complete only when schema, target identity, effects, permissions, privacy/egress behavior, cancellation, retry class, verification, failure handling, logging, and relevant real-platform tests exist.

A nice interface, a function that returns without throwing, or a model confidently saying "Done" does not meet this definition.

## 22. Working with Codex without losing scope

Use one self-contained specification, one current milestone plan, and one evidence log. A phase-oriented workflow with explicit checks and progress evidence is consistent with OpenAI's published Codex development guidance. [S23]

### 22.1 Persistent repository instructions

Have Codex create a concise `AGENTS.md` covering:

- the specification path and current approved milestone;
- model/provider independence and no execution outside the broker;
- fake-by-default behavior and no real integration in M0;
- commands for tests/checks and rules for local dependencies;
- preserving user work and requesting approval for scope/security changes;
- reporting actual results rather than inferred completion.

Do not place the entire specification in `AGENTS.md`. Do not create skill/plugin packages or unrelated editor configuration for this task.

### 22.2 Normal implementation session

Read the applicable instructions and current code. Produce a short plan, then implement within the approved scope. Do not stop after scaffolding. Resolve ordinary implementation details conservatively and record material choices.

Ask only for genuine blockers, consequential setup permission, or scope/security changes. Do not repeatedly ask the user to reconfirm known hardware or the chosen local-only architecture.

Run tests, inspect the diff, update implementation status, and stop at the milestone boundary. Do not automatically begin the next milestone because earlier tests passed.

### 22.3 Development permissions are not runtime permissions

Running project tests or installing an approved project dependency while building the application does not require adding a shell/install tool to JARVIS. Conversely, the fact that a coding environment has broad access does not justify giving the finished agent the same access.

Do not change global security settings, disable safeguards, expose network services, publish code, push to remotes, or create automatic-start entries without explicit user permission. Preserve any unrelated files found in a supposedly fresh repository.

### 22.4 Progress updates must remain evidence-based

A task can be "implementation complete; live validation pending." That is a useful and honest state. Never rename it "fully working" to make a handoff look better.

When a provider/profile changes, rerun affected evaluations. When a native adapter changes, rerun its Windows tests. When permissions change, rerun denial/cancellation/recovery regressions.

## 23. Non-negotiable implementation rules

| ID | Rule |
|---|---|
| CORE-01 | The model proposes; only the trusted broker dispatches actions. |
| CORE-02 | Complete decisions and arguments are strictly validated and registry-resolved. |
| CORE-03 | Every task has an explicit scope, revision, budget, and termination path. |
| CORE-04 | Claimed action completion requires matching observed evidence. |
| CORE-05 | A model name or response cannot grant permissions or expand the tool registry. |
| MODEL-01 | Providers and model-specific formats stay outside domain, policy, and adapters. |
| MODEL-02 | Unknown model capabilities remain unknown until inspected/tested. |
| MODEL-03 | Model/profile changes require qualification; no hidden fake or cloud fallback. |
| MODEL-04 | Native tool calling is optional; trusted validation is mandatory. |
| MODEL-05 | One active text profile per task initially; no automatic multi-model orchestration. |
| AUTH-01 | Task scope is narrower than or equal to standing grants, never derived solely from a proposal. |
| AUTH-02 | Exact approvals bind effects, targets, content, revisions, versions, and expiry. |
| AUTH-03 | Unknown effects are not low risk; generic clicking cannot bypass semantic restrictions. |
| AUTH-04 | The agent cannot approve itself or manipulate its own emergency/security controls. |
| AUTH-05 | Voice, web pages, documents, and notifications cannot create owner authority. |
| EXEC-01 | Record durable intent before effects; uncertain effects are not blindly replayed. |
| EXEC-02 | One physical-input owner; revalidate targets and pause on user takeover. |
| EXEC-03 | Cancellation stops new admissions, not already completed or irretrievable effects. |
| EXEC-04 | Retries obey effect-specific rules and task budgets. |
| EXEC-05 | Undo preserves intervening user changes and does not promise impossible rollback. |
| DATA-01 | Inference/personal memory remain local; online tools disclose only authorized data. |
| DATA-02 | Secrets, raw prompts, screen/audio artifacts, and authenticated state are not ordinary logs or Git data. |
| DATA-03 | Derived private information retains its disclosure restrictions. |
| DATA-04 | Memory has inspect/correct/export/delete and derived-index handling. |
| WEB-01 | Current facts require suitable retrieval and source/effective timestamps. |
| WEB-02 | No login, CAPTCHA, DRM, secure-desktop, or anti-cheat bypass. |
| WEB-03 | Public fetch tools cannot reach local/private services without separate authorization. |
| DEV-01 | M0 has no real model, real application control, or runtime network activity. |
| DEV-02 | M1 requires actual local-model validation through JARVIS, with actions still simulated. |
| DEV-03 | Do not silently weaken tests, requirements, or security to produce a pass. |
| DEV-04 | Report what was tested and where; mocks are not Windows or live-model evidence. |
| DEV-05 | A later feature description is not permission to implement it before its milestone. |

## 24. First Codex prompt

Place this file in the root of a new repository, open that folder in Codex, and send the prompt below. The companion `JARVIS_Codex_First_Prompt.md` contains the same prompt for easy copying.

```text
We are starting JARVIS from scratch in this repository.

Read JARVIS_Project_Specification.md completely, in multiple reads if
needed. Read any applicable AGENTS.md instructions and inspect the
existing directory before changing files. Preserve unrelated work.

Use the new specification for this restart. Do not combine requirements
from earlier JARVIS architecture files or assume any milestone is done.

IMPLEMENT M0 ONLY: THE SAFE SIMULATED CORE.

Project context:
- I am developing on a lower-spec Windows laptop. Do not assume the
  hardware of my main PC is available here.
- My future main PC has an RTX 4070, 32 GB RAM, and a Ryzen 5 5600X.
- The architecture must support different local models through profiles
  and provider adapters, not hardcoded model-specific execution logic.
- Real Ollama integration and live model setup are M1, not this task.

First demonstrate:
"Open my registered text editor."

Use a scripted fake model and fake desktop, but route the request through
real application logic:
request identity and target scope -> structured proposal -> strict parser
-> registry -> authorization -> durable action intent -> cancellation gate
-> fake execution -> independent verification -> truthful simulated result.

Implement the smallest maintainable vertical slice:

1. Create the Python project, src layout, project-local dependency setup,
   generated lock strategy, README, and .gitignore. Use the specification's
   Python baseline or document a compatible installed version.

2. Create a concise AGENTS.md pointing to the specification and recording
   M0 scope, essential invariants, and actual test/check commands. Create
   docs/IMPLEMENTATION_PLAN.md and docs/BUILD_LOG.md. Do not duplicate the
   whole specification or generate empty modules for future milestones.

3. Implement typed domain contracts, a provider interface, configurable
   fake provider, strict decision parsing, a reviewed capability registry,
   task state/revision handling, scoped authorization, exact-action approval
   validation where applicable, and an execution broker.

4. Implement SQLite persistence for tasks, action intents, attempts, and
   audit events. Add bounded execution, cancellation, duplicate-request
   handling, verification, and conservative unknown-outcome recovery.
   Inject the clock and adapters so tests are deterministic.

5. Add runnable CLI scenarios for open-editor success, permission denial,
   cancellation, and uncertain recovery. Label all actions SIMULATED.
   The demo must change and verify fake state, not simply print success.

6. Test successful execution, unauthorized targets, malformed/duplicate-key
   JSON, unknown tools, invalid arguments, stale revisions, changed or
   expired approvals, cancellation and late replies, duplicate deliveries,
   verification failure, crash uncertainty, and untrusted content attempting
   to expand scope. Assert zero execution where an action is denied.

7. Test the same broker with two fake-provider configurations to demonstrate
   model independence. Keep laptop/desktop model examples in configuration,
   not hardcoded into domain, policy, or tool code. This is not a claim of
   compatibility with real models yet.

Boundaries:
- No Ollama installation, model downloads, cloud inference, or runtime
  network requests in M0.
- No real application launching, mouse/keyboard input, browser control,
  screenshots, microphone access, personal files, or external accounts.
- No unrestricted runtime shell, generated-code execution, or self-installing
  plugins. Normal project-local development commands and tests are allowed
  within existing permissions.
- Do not request administrator privileges, alter global security settings,
  enable startup services, or push/publish the repository.
- Do not weaken requirements or remove valid tests to obtain a pass.

Give a brief implementation plan, then implement and test; do not stop at
planning or scaffolding. Resolve ordinary details conservatively. Ask only
for genuine blockers, scope changes, or consequential setup permission.

Before finishing, run the relevant tests/checks, inspect the diff, and
update the implementation plan and evidence log with actual results.

Report:
1. What was implemented and which files matter.
2. Exact PowerShell commands to set up, run the demos, and run tests.
3. Commands actually executed and their results.
4. What is simulated, incomplete, blocked, or not tested on Windows.
5. Whether M0's exit gate is met and what remains before M1.

Stop at M0 for review. Do not begin real-model integration or Windows control.
```

## 25. Sources and verification notes

Sources were consulted on 9 October 2026. These references support external product/API behavior, not claims that JARVIS has already been built or that a particular model passes its tests. Verify current dependency compatibility, model metadata, and service policies again at the relevant implementation milestone.

The Qwen examples are continuity candidates for the user's laptop-to-desktop workflow, not a survey or ranking of all current local models. No GPU benchmark, actual Windows integration test, or end-to-end JARVIS run was performed while writing this specification.

[S01]: https://developers.openai.com/codex/guides/agents-md
[S02]: https://docs.ollama.com/windows
[S03]: https://docs.ollama.com/faq
[S04]: https://docs.ollama.com/capabilities/structured-outputs
[S05]: https://docs.ollama.com/capabilities/tool-calling
[S06]: https://docs.ollama.com/capabilities/thinking
[S07]: https://docs.ollama.com/context-length
[S08]: https://ollama.com/library/qwen3
[S09]: https://docs.pydantic.dev/latest/concepts/strict_mode/
[S10]: https://learn.microsoft.com/en-us/windows/win32/winauto/uiauto-uiautomationoverview
[S11]: https://learn.microsoft.com/en-us/windows/win32/services/interactive-services
[S12]: https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-sendinput
[S13]: https://playwright.dev/python/docs/auth
[S14]: https://playwright.dev/python/docs/locators
[S15]: https://developer.spotify.com/documentation/web-api/reference/start-a-users-playback
[S16]: https://sqlite.org/lang_transaction.html
[S17]: https://sqlite.org/backup.html
[S18]: https://github.com/SYSTRAN/faster-whisper
[S19]: https://github.com/OHF-Voice/piper1-gpl
[S20]: https://github.com/dscripka/openWakeWord
[S21]: https://www.python-httpx.org/environment_variables/
[S22]: https://docs.ollama.com/api/chat
[S23]: https://developers.openai.com/cookbook/examples/codex/iterating-development-workflows-with-codex

| Reference | Primary source | Used for |
|---|---|---|
| S01 | [OpenAI: Codex repository instructions][S01] | `AGENTS.md` recognition and instruction workflow |
| S02 | [Ollama: Windows][S02] | Native Windows runtime and setup |
| S03 | [Ollama: FAQ][S03] | Local-only mode, cloud disabling, and bind configuration |
| S04 | [Ollama: structured outputs][S04] | Schema-constrained response mechanism |
| S05 | [Ollama: tool calling][S05] | Native tool proposal mechanism |
| S06 | [Ollama: thinking][S06] | Model-specific controls and separate reasoning/content fields |
| S07 | [Ollama: context length][S07] | Context configuration and memory considerations |
| S08 | [Ollama: Qwen3 catalog][S08] | Named variant availability and approximate download sizes |
| S09 | [Pydantic: strict mode][S09] | Boundary validation and coercion behavior |
| S10 | [Microsoft: UI Automation overview][S10] | Desktop accessibility automation |
| S11 | [Microsoft: interactive services][S11] | Service/interactive-session separation |
| S12 | [Microsoft: SendInput][S12] | Input injection and privilege boundaries |
| S13 | [Playwright: authentication][S13] | Sensitive stored browser state |
| S14 | [Playwright: locators][S14] | Semantic browser targeting |
| S15 | [Spotify: start/resume playback][S15] | Playback prerequisites and API behavior |
| S16 | [SQLite: transactions][S16] | Internal state transaction semantics |
| S17 | [SQLite: backup API][S17] | Consistent database backup |
| S18 | [SYSTRAN: faster-whisper][S18] | Candidate local speech transcription engine |
| S19 | [Open Home Foundation: Piper][S19] | Candidate local speech synthesis engine |
| S20 | [openWakeWord upstream][S20] | Candidate wake-word engine and Windows notes |
| S21 | [HTTPX: environment variables][S21] | Controlling environment-derived client configuration |
| S22 | [Ollama: chat API][S22] | Provider request/response fields |
| S23 | [OpenAI: iterative Codex workflows][S23] | Phase-scoped implementation and evidence recording |
