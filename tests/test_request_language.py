"""Natural request fields and semantic proposals remain inside owner/broker ceilings."""

import hashlib
import json
import socket
import subprocess

import pytest
from test_media import ChoiceProvider

from jarvis.application_data import ApplicationsConfig
from jarvis.application_fake import FakeApplicationPlatform
from jarvis.application_tools import attach
from jarvis.bootstrap import ManualClock, build
from jarvis.domain import Denied, State
from jarvis.media_data import MediaConfig
from jarvis.media_fake import FakeBrowserProvider
from jarvis.models import ModelReply, Profile


class LanguageProvider(ChoiceProvider):
    def __init__(self):
        super().__init__()
        self.meaning = {
            "kind": "request_meaning",
            "domain": "media",
            "operation": "play",
            "service": "spotify",
            "target": "Fav Jpop",
        }
        self.language_hook = lambda: None
        self.language_calls = 0

    def generate(self, request, cancel):
        if request.decision_boundary == "request-language-v1":
            self.language_calls += 1
            self.language_hook()
            raw = json.dumps(self.meaning).encode()
        elif request.decision_boundary == "applications-choice-v1":
            raw = json.dumps(
                {
                    "kind": "application_choice",
                    **{
                        k: v["const"]
                        for k, v in request.schema["properties"].items()
                        if "const" in v
                    },
                }
            ).encode()
        elif request.decision_boundary is None:
            self.requests.append(request)
            raw = b'{"kind":"say","text":"Synthetic capability explanation."}'
        else:
            return super().generate(request, cancel)
        return ModelReply(request.request_id, request.task_id, request.revision, raw, "synthetic")


@pytest.fixture
def language_setup(tmp_path, monkeypatch):
    monkeypatch.setattr(socket, "socket", lambda *a, **k: pytest.fail("Network in offline test"))
    monkeypatch.setattr(subprocess, "Popen", lambda *a, **k: pytest.fail("Process in offline test"))
    clock = ManualClock()
    model, fake, platform = (
        LanguageProvider(),
        FakeBrowserProvider(clock),
        FakeApplicationPlatform(),
    )
    platform.add_app("Studio Note")
    fake.catalog = [
        ("a" * 22, "Fav Jpop", "Test owner"),
        ("b" * 22, "my fav jpop", "Another owner"),
        ("c" * 22, "Jpop FAVS", "Other owner"),
    ]
    profile = Profile(
        profile_name="language-fixture",
        model_identity="scripted",
        prompt_version="planner-m2-v10",
        decision_version="decision-m2-v1",
        reply='{"kind":"say","text":"Hello"}',
    )
    broker = build(
        tmp_path / "j.sqlite",
        profile,
        clock,
        provider=model,
        media_config=MediaConfig(
            enabled=True, youtube=True, spotify=True, spotify_backend="desktop"
        ),
        browser_provider=fake,
    )
    chat = attach(broker, ApplicationsConfig(enabled=True), platform=platform)
    yield broker, chat, fake, model, platform
    broker.media.close()
    broker.store.close()


@pytest.mark.parametrize(
    "text",
    [
        "play playlist fav jpop",
        "play playlist fav jpop spotify",
        "play playlist fav jpop on spotify",
        "Could you please put on playlist Fav Jpop using Spotify?",
        "I'd like to listen to playlist Fav Jpop on Spotify",
        "Find Spotify for playlist Fav Jpop then play it",
    ],
)
def test_service_is_a_field_and_unique_exact_playlist_wins(language_setup, text):
    broker, chat, fake, model, _ = language_setup
    result = chat.submit(text)
    assert result.state == State.SUCCEEDED
    assert fake.execution_count == 3
    assert broker.media.observation.title == "Fav Jpop"
    assert broker.media.observation.state == "playing"
    assert model.language_calls == 0  # Straightforward requests keep the fast route.


def test_duplicate_spotify_titles_use_owner_selected_first_result(language_setup):
    broker, chat, fake, _, _ = language_setup
    fake.catalog = [("a" * 22, "Fav Jpop", "One"), ("b" * 22, "Fav Jpop", "Two")]
    result = chat.submit("Play playlist Fav Jpop")
    assert result.state == State.SUCCEEDED and fake.execution_count == 3
    assert broker.media.observation.item_id == "a" * 22
    assert "Which" not in (result.display_message or result.message)


def test_youtube_artist_must_match_creator_metadata(language_setup):
    broker, chat, fake, _, _ = language_setup
    result = chat.submit("Play Fav Jpop by Test owner on YouTube")
    assert result.state == State.SUCCEEDED and fake.execution_count == 3
    assert broker.media.observation.title == "Fav Jpop"


def test_youtube_artist_in_title_does_not_substitute_for_creator(language_setup):
    _, chat, fake, _, _ = language_setup
    fake.catalog = [("a" * 22, "Fav Jpop Test owner", "Someone else")]
    result = chat.submit("Play Fav Jpop by Test owner on YouTube")
    assert fake.execution_count == 1 and "Which" in result.display_message


@pytest.mark.parametrize("service", ["spotify", "youtube"])
def test_negative_word_in_song_title_is_not_a_negated_command(language_setup, service):
    broker, chat, fake, model, _ = language_setup
    fake.catalog = [("a" * 22, "Never Gonna Give You Up", "Rick Astley")]
    model.meaning.update(service=service, target="Never Gonna Give You Up by Rick Astley")
    result = chat.submit(
        "Could you put Never Gonna Give You Up by Rick Astley on for me using " + service
    )
    assert result.state == State.SUCCEEDED and fake.execution_count == 3
    assert broker.media.observation.title == "Never Gonna Give You Up"


def test_semantic_media_target_is_literal_and_every_phase_is_brokered(language_setup):
    broker, chat, fake, model, _ = language_setup
    text = "Could you put the playlist Fav Jpop on for me using Spotify?"
    result = chat.submit(text, "semantic")
    assert result.state == State.SUCCEEDED and model.language_calls == 1
    assert fake.execution_count == 3
    assert broker.media.observation.title == "Fav Jpop"
    assert (
        broker.store.db.execute("SELECT COUNT(*) FROM actions WHERE state='VERIFIED'").fetchone()[0]
        == 3
    )
    rows = broker.store.db.execute("SELECT redacted_payload_json FROM events").fetchall()
    assert all("Fav Jpop" not in row[0] for row in rows)  # Only span indices/hash metadata.
    again = chat.submit(text, "semantic")
    assert (
        again.task_id == result.task_id and model.language_calls == 1 and fake.execution_count == 3
    )
    with pytest.raises(Denied):
        chat.submit(text + " please", "semantic")


def test_same_interpretation_boundary_handles_browser_and_apps(language_setup):
    broker, chat, fake, model, platform = language_setup
    model.meaning.update(service="youtube")
    assert chat.submit("Put Fav Jpop on YouTube for me").state == State.SUCCEEDED
    assert fake.execution_count == 3 and broker.media.service == "youtube"
    model.meaning.update(domain="application", operation="open", service="", target="Studio Note")
    result = chat.submit("Could you pull up Studio Note for me?")
    assert result.state == State.SUCCEEDED and len(platform.windows) == 1
    assert model.language_calls == 2


@pytest.mark.parametrize(
    "change",
    [
        {"target": "Invented private query"},
        {"operation": "close"},
        {"service": "youtube"},
        {"domain": "application", "operation": "open"},
        {"unexpected": "field"},
    ],
)
def test_model_cannot_change_target_operation_service_or_schema(language_setup, change):
    _, chat, fake, model, platform = language_setup
    model.meaning.update(change)
    result = chat.submit("Put playlist Fav Jpop on for me using Spotify")
    assert (
        result.state == State.WAITING_INPUT and fake.execution_count == 0 and platform.windows == []
    )


@pytest.mark.parametrize(
    "text",
    [
        "Don't put playlist Fav Jpop on Spotify",
        "How do I put playlist Fav Jpop on Spotify?",
        "Explain how to play playlist Fav Jpop on Spotify",
        "If I ask you to play Fav Jpop on Spotify",
        "Put file:///private/secret.txt on Spotify for me",
        "Put playlist Fav Jpop on Spotify for me but don't play it",
    ],
)
def test_explanation_negation_and_private_data_do_not_enter_semantic_actions(language_setup, text):
    _, chat, fake, model, platform = language_setup
    chat.submit(text)
    assert model.language_calls == 0 and fake.execution_count == 0 and platform.windows == []


def test_cancelled_interpretation_never_searches_or_opens(language_setup):
    broker, chat, fake, model, _ = language_setup
    stop = []
    broker.cancel_requested = lambda: bool(stop)
    model.language_hook = lambda: stop.append(True)
    result = chat.submit("Put playlist Fav Jpop on for me using Spotify")
    assert result.state == State.CANCELLED and fake.execution_count == 0


@pytest.mark.parametrize("change", ["selection", "deadline", "profile"])
def test_obsolete_interpretation_never_executes(language_setup, change):
    broker, chat, fake, model, _ = language_setup
    if change == "selection":
        model.language_hook = lambda: setattr(broker.media, "current_reference", "changed")
    elif change == "deadline":
        model.language_hook = lambda: broker.clock.advance(broker.profile.task_seconds + 1)
    else:
        model.language_hook = lambda: setattr(
            broker, "profile", broker.profile.model_copy(update={"model_identity": "changed"})
        )
    result = chat.submit("Put playlist Fav Jpop on for me using Spotify")
    assert result.state == State.WAITING_INPUT and fake.execution_count == 0


def test_real_semantic_actions_require_their_own_model_qualification(language_setup):
    broker, chat, fake, model, _ = language_setup
    broker.media.real = True
    result = chat.submit("Put playlist Fav Jpop on for me using Spotify")
    assert result.state == State.WAITING_INPUT and model.language_calls == 0
    assert fake.execution_count == 0


def test_service_window_request_is_not_a_media_title():
    from jarvis.media_language import named_media_request

    assert named_media_request("Open Spotify app") is None
    assert named_media_request("Open YouTube window") is None


@pytest.mark.parametrize(
    "text",
    [
        "Search the web for Spotify news",
        "Look up current exchange rates for me",
        "Find information about YouTube for me",
        "Search online for the Spotify desktop app",
    ],
)
def test_read_domains_are_not_captured_by_action_interpretation(language_setup, text):
    from jarvis.media_language import named_media_request
    from jarvis.request_language import normalize

    broker, chat, fake, model, _ = language_setup
    broker.media.service = "youtube"
    broker.media.owner_session = broker.grant.session
    assert normalize(chat.original, text) == text
    assert named_media_request(text) is None
    assert broker.registry.scope_for(broker.grant.session, text).app_id != "media"
    assert model.language_calls == 0 and fake.execution_count == 0


def test_conversation_sees_actual_configured_capabilities(language_setup):
    _, chat, fake, model, _ = language_setup
    assert chat.submit("Can you control Spotify and find playlists?").state == State.ANSWERED
    system = model.requests[-1].messages[0].text
    assert '"spotify_search":true' in system.replace(" ", "")
    assert "override historical Notepad-only" in system
    assert fake.execution_count == 0


def test_wording_qualification_cannot_be_used_for_another_contract_or_fake_pass(
    language_setup, tmp_path
):
    from jarvis.language_evaluation import CORPUS, contract_hash, qualified

    broker, _, _, _, _ = language_setup
    corpus = json.loads(CORPUS.read_bytes())
    metadata = {"ready": True, "digest": "synthetic", "runtime_version": "synthetic"}
    report = {
        "version": "request-language-evaluation-v1",
        "execution_mode": "simulation",
        "passed": True,
        "profile": broker.profile.model_dump(),
        "metadata": metadata,
        "contract_sha256": contract_hash(),
        "corpus_sha256": hashlib.sha256(CORPUS.read_bytes()).hexdigest(),
        "gate": corpus["gate"],
        "total": len(corpus["cases"]),
        "correct": len(corpus["cases"]),
        "records": [
            {
                "id": c["id"],
                "correct": True,
                "postconditions_verified": True,
                "unauthorized_dispatches": 0,
                "media_calls": c.get("media_calls", 0),
                "app_calls": c.get("app_calls", 0),
            }
            for c in corpus["cases"]
        ],
    }
    path = tmp_path / "synthetic-report.json"
    path.write_text(json.dumps(report))
    assert qualified(path, broker.profile, metadata)
    assert not qualified(path, broker.profile, {**metadata, "digest": "another model"})
    assert not qualified(path, broker.profile.model_copy(update={"context_bytes": 9999}), metadata)
    report["records"][0]["media_calls"] = 0
    path.write_text(json.dumps(report))
    assert not qualified(path, broker.profile, metadata)
    report["records"][0]["media_calls"] = 3
    report["contract_sha256"] = "old code"
    path.write_text(json.dumps(report))
    assert not qualified(path, broker.profile, metadata)


def test_wording_gate_observes_actual_state_instead_of_trusting_success(language_setup):
    from jarvis.domain import TaskResult
    from jarvis.language_evaluation import observe

    broker, _, fake, _, platform = language_setup
    fake.execution_count = 3
    result = TaskResult("synthetic", State.SUCCEEDED, "claimed success")
    row = observe(
        {"id": "independent", "media_calls": 3, "media_state": "playing", "title": "Fav Jpop"},
        result,
        broker,
        fake,
        platform,
    )
    assert row["correct"] is False and row["postconditions_verified"] is False
