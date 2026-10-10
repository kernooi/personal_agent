"""Currency registration and adapter on the existing broker execution path."""

from dataclasses import asdict
from datetime import datetime

from jarvis.currency_cache import QuoteCache
from jarvis.currency_provider import FixtureProvider, FrankfurterProvider
from jarvis.currency_router import route
from jarvis.domain import Denied, Evidence, PreparedAction, Scope
from jarvis.policy import POLICY_VERSION
from jarvis.public_catalogue import CatalogueCache, parse_catalogue
from jarvis.public_data import (
    CurrencyArguments,
    PublicDataError,
    canonical,
    parse_quote,
    render,
    validate_quote,
)
from jarvis.tools import digest


class CurrencyRegistry:
    def __init__(self, underlying, adapter):
        self.underlying, self.currency = underlying, adapter
        self.route = None
        self.context = None
        self.context_session = None

    def completed(self, task, resolved):
        from jarvis.domain import State

        if resolved and resolved.pending_pair and task.state == State.WAITING_INPUT:
            self.context = resolved.pending_pair
        elif task.scope.app_id == "currency" and task.state == State.SUCCEEDED:
            args = CurrencyArguments.model_validate_json(task.scope.window_ref)
            self.context = (args.base, args.quote)
        else:
            self.context = None
            self.currency.last_quote = None
        self.context_session = task.scope.session

    def __getattr__(self, name):
        return getattr(self.underlying, name)

    @property
    def intent(self):
        if self.route and self.route.kind != "ordinary":
            return None
        return getattr(self.underlying, "intent", None)

    def scope_for(self, session, text):
        previous = self.currency.last_quote if self.currency.session == session else None
        context = self.context if self.context_session == session else None
        self.route = route(text, previous, context)
        if self.route.kind == "currency":
            args = self.route.arguments
            effect = {
                "latest": "public_read",
                "supplied": "local_calculate",
                "identity": "local_calculate",
                "source": "read_evidence",
            }[args.operation]
            return Scope(session, "currency", effect, canonical(args))
        if self.route.kind != "ordinary":
            return Scope(session, "none")
        return self.underlying.scope_for(session, text)

    def prepare(self, task, proposal, grant):
        if task.scope.app_id != "currency":
            return self.underlying.prepare(task, proposal, grant)
        if proposal.capability != "currency.quote" or proposal.app_id != "currency":
            raise Denied("Currency task cannot authorize another tool")
        args = CurrencyArguments.model_validate_json(proposal.window_ref, strict=True)
        if canonical(args) != task.scope.window_ref:
            raise Denied("Currency proposal differs from owner scope")
        effect = {
            "latest": "public_read",
            "supplied": "local_calculate",
            "identity": "local_calculate",
            "source": "read_evidence",
        }[args.operation]
        action = PreparedAction(
            task.task_id,
            task.revision,
            "currency.quote",
            "currency",
            "reviewed:frankfurter_ecb:v1",
            task.scope.session,
            (effect,),
            "currency-adapter-v1",
            POLICY_VERSION,
            grant.grant_id,
            grant.version,
            min(task.deadline, grant.expires_at),
            "",
            canonical(args),
        )
        return PreparedAction(**{**asdict(action), "digest": digest(action)})

    def validate(self, action):
        if action.capability != "currency.quote":
            return self.underlying.validate(action)
        if (
            action.app_id != "currency"
            or action.target_identity != "reviewed:frankfurter_ecb:v1"
            or action.adapter_version != "currency-adapter-v1"
            or digest(action) != action.digest
            or action.policy_version != POLICY_VERSION
        ):
            raise Denied("Currency prepared action changed")
        args = CurrencyArguments.model_validate_json(action.window_ref, strict=True)
        if canonical(args) != action.window_ref:
            raise Denied("Currency arguments changed")
        expected = {
            "latest": "public_read",
            "supplied": "local_calculate",
            "identity": "local_calculate",
            "source": "read_evidence",
        }[args.operation]
        if action.effects != (expected,):
            raise Denied("Currency effect changed")
        if args.operation == "latest" and self.currency.config.mode == "disabled":
            raise PublicDataError("NETWORK_DISABLED")


class CurrencyAdapter:
    evidence_source = "currency-record-validator-v1"
    evidence_kind = "validated_public_quote"

    def __init__(self, clock, config, provider=None, cache_path=None):
        self.clock, self.config = clock, config
        self.provider = provider or FrankfurterProvider()
        self.cache = QuoteCache(config, cache_path)
        self.catalogue_cache = CatalogueCache(
            config, cache_path.with_name("public-currencies.json") if cache_path else None
        )
        if isinstance(self.provider, FixtureProvider):
            # An explicit synthetic fixture supplies its catalogue without networking.
            raw = self.provider.supported_currencies(
                config, lambda: False, self.clock.now() + config.timeout_seconds
            )
            self.catalogue_cache.put(
                parse_catalogue(raw, config, self.clock.now(), synthetic=True), self.clock.now()
            )
        self.last_quote = None
        self.last_status = None
        self.last_quote_status = None
        self.last_quote_failure = None
        self.observation = None
        self.failure = None
        self.execution_calls = 0
        self.observation_calls = 0
        self.cancel = lambda: False
        self.session = None

    def supported_currencies(self, action, gate, *, allow_network):
        self.catalogue_cache.config = self.config
        if self.config.mode == "disabled" and isinstance(self.provider, FixtureProvider):
            # Explicit fixtures remain synthetic during their local-only disabled tests.
            self.catalogue_cache.config = self.config.model_copy(update={"mode": "fixture"})
        record = self.catalogue_cache.get(self.clock.now())
        if record is None:
            if not allow_network:
                raise PublicDataError("CURRENCY_METADATA_REQUIRED_NO_LOOKUP")
            gate()
            raw = self.provider.supported_currencies(self.config, self.cancel, action.expires_at)
            if self.cancel():
                raise PublicDataError("CANCELLED")
            if self.clock.now() >= action.expires_at:
                raise PublicDataError("DEADLINE_EXCEEDED")
            record = parse_catalogue(
                raw, self.config, self.clock.now(), synthetic=self.config.mode == "fixture"
            )
            self.catalogue_cache.put(record, self.clock.now())
        return record.currencies

    def execute(self, action, admission_gate):
        admission_gate()
        args = CurrencyArguments.model_validate_json(action.window_ref, strict=True)
        self.observation = None
        if args.operation != "source":
            self.failure = None
        self.execution_calls += 1
        if args.operation != "source":
            # Local calculations never make a network call. A cold/expired catalogue
            # requires a separate latest-rate request before local calculations.
            codes = self.supported_currencies(
                action, admission_gate, allow_network=args.operation == "latest"
            )
            if args.base not in codes or args.quote not in codes:
                raise PublicDataError("UNSUPPORTED_CURRENCY")
        if args.operation in {"supplied", "identity"}:
            self.last_status = "user supplied" if args.operation == "supplied" else "local identity"
            self.last_quote = None  # A supplied rate has no public source to cite.
            return
        if args.operation == "source":
            if self.last_quote is None or self.session != action.session:
                raise PublicDataError("UNKNOWN_CITATION")
            self.observation = self.last_quote
            # Preserve the fetch/cache provenance and stale warning on follow-ups.
            self.last_status, self.failure = self.last_quote_status, self.last_quote_failure
            if (
                self.last_quote.freshness != "dated_stale"
                and self.clock.now()
                >= datetime.fromisoformat(self.last_quote.expires_at_utc).timestamp()
            ):
                self.last_status = "dated session evidence"
            return
        if self.config.mode == "disabled":
            raise PublicDataError("NETWORK_DISABLED")
        now = self.clock.now()
        observation = None if args.refresh else self.cache.get(args.base, args.quote, now)
        self.last_status = "fresh cache"
        if observation is None:
            # Recheck the broker gate immediately before the supervised outbound job.
            admission_gate()
            try:
                raw = self.provider.fetch(
                    args.base, args.quote, self.config, self.cancel, action.expires_at
                )
                if self.cancel():
                    raise PublicDataError("CANCELLED")
                if self.clock.now() >= action.expires_at:
                    raise PublicDataError("DEADLINE_EXCEEDED")
                observation = parse_quote(
                    raw,
                    args.base,
                    args.quote,
                    self.config,
                    self.clock.now(),
                    synthetic=self.config.mode == "fixture",
                )
                self.cache.put(observation, self.clock.now())
                self.last_status = "fixture" if self.config.mode == "fixture" else "live fetch"
            except PublicDataError as exc:
                if exc.code in {"CANCELLED", "DESTINATION_DENIED", "PEER_MISMATCH", "URL_DENIED"}:
                    raise
                observation = self.cache.get(args.base, args.quote, self.clock.now(), stale=True)
                if observation is None:
                    raise
                observation = observation.model_copy(update={"freshness": "dated_stale"})
                self.last_status, self.failure = "stale cache", exc.code
        self.observation = observation

    def observe(self, action):
        self.observation_calls += 1
        args = CurrencyArguments.model_validate_json(action.window_ref, strict=True)
        if self.cancel():
            raise PublicDataError("CANCELLED")
        if self.clock.now() >= action.expires_at:
            raise PublicDataError("DEADLINE_EXCEEDED")
        observation = self.observation
        if args.operation not in {"supplied", "identity"}:
            if (
                observation is None
                or observation.base != args.base
                or observation.quote != args.quote
            ):
                raise PublicDataError("PAIR_MISMATCH")
            # Independent validation before publishing, including cached records.
            validate_quote(observation, self.config, self.clock.now())
            if self.config.mode == "enabled" and observation.sensitivity != "public":
                raise PublicDataError("SYNTHETIC_RECORD_DENIED")
            if args.operation != "source":
                codes = self.supported_currencies(action, lambda: None, allow_network=False)
                if args.base not in codes or args.quote not in codes:
                    raise PublicDataError("UNSUPPORTED_CURRENCY")
            self.last_quote, self.session = observation, action.session
            if args.operation != "source":
                self.last_quote_status, self.last_quote_failure = self.last_status, self.failure
        else:
            codes = self.supported_currencies(action, lambda: None, allow_network=False)
            if args.base not in codes or args.quote not in codes:
                raise PublicDataError("UNSUPPORTED_CURRENCY")
        return Evidence(
            action.target_identity,
            action.session,
            self.clock.now(),
            None,
            self.evidence_source,
            "tool_output",
            "public" if observation else "personal",
            self.evidence_kind,
            True,
            "",
            observation.model_dump_json()
            if observation
            else "local calculation; no public quote lookup",
        )

    def success_message(self, action):
        args = CurrencyArguments.model_validate_json(action.window_ref, strict=True)
        return render(args, self.observation, status=self.last_status, failure=self.failure)

    def concise_message(self, action):
        args = CurrencyArguments.model_validate_json(action.window_ref, strict=True)
        return render(
            args, self.observation, status=self.last_status, failure=self.failure, concise=True
        )


def load_public_config(path):
    import tomllib

    from jarvis.public_data import PublicConfig

    return PublicConfig.model_validate(
        tomllib.loads(path.read_text(encoding="utf-8-sig")), strict=True
    )
