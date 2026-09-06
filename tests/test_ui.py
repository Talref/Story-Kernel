from __future__ import annotations

from dataclasses import dataclass, field

from typer.testing import CliRunner

from story_kernel.cli import app
from story_kernel.contracts import (
    ModelInfo,
    ProviderDiagnostics,
    ProviderMessage,
    ProviderResponse,
    ToolCall,
)
from story_kernel.provider import ProviderError
from story_kernel.ui import UIController, build_interface, create_harness


@dataclass
class UIProvider:
    name: str = "fake"
    responses: list[ProviderResponse] = field(default_factory=list)

    def list_models(self):
        return [
            ModelInfo(
                id="fake/medium", name="Medium", capabilities={"tool_calling": True}
            )
        ]

    def complete(self, _request):
        return self.responses.pop(0)


def test_ui_controller_chat_new_conversation_and_world_reset(tmp_path):
    provider = UIProvider(
        responses=[
            ProviderResponse(
                model="fake/medium",
                message=ProviderMessage(
                    role="assistant",
                    tool_calls=[
                        ToolCall(
                            id="call:1",
                            name="create_object",
                            arguments={
                                "object_type": "fixture.Fact",
                                "attributes": {"statement": "persistent"},
                            },
                        )
                    ],
                ),
            ),
            ProviderResponse(
                model="fake/medium",
                message=ProviderMessage(role="assistant", content="Stored."),
            ),
        ]
    )
    harness = create_harness(tmp_path / "ui.db", provider)
    controller = UIController(harness)
    conversation_id, _browser, history, _model, _status = controller.new_conversation(
        "fake/medium"
    )

    _, staged_history, active_id, pending, _browser, _status = controller.stage_message(
        "Remember this", history, conversation_id, "fake/other"
    )
    assert staged_history[-1] == {"role": "user", "content": "Remember this"}
    assert len(provider.responses) == 2

    history, pending, _status = controller.complete_message(
        pending, staged_history, active_id
    )
    assert pending is None
    assert len(provider.responses) == 0
    assert active_id == conversation_id
    assert history[-1] == {"role": "assistant", "content": "Stored."}
    assert harness.state.get_conversation(active_id)["model"] == "fake/medium"
    assert harness.state.world_snapshot()["objects"]

    new_id, _browser, new_history, _model, _status = controller.new_conversation(
        "fake/medium"
    )
    assert new_id != conversation_id
    assert new_history == []
    assert harness.state.world_snapshot()["objects"]

    controller.reset_world()
    assert harness.state.world_snapshot()["objects"] == []
    assert harness.state.get_conversation(new_id)["model"] == "fake/medium"


def test_bootstrap_restores_active_conversation_transcript_and_model(tmp_path):
    database = tmp_path / "restart.db"
    first_harness = create_harness(database, UIProvider())
    first = first_harness.state.create_conversation("fake/original", provider="fake")
    first_harness.state.append_message(first["id"], "user", "Still here?")
    first_harness.state.append_message(first["id"], "assistant", "Still here.")

    restarted = create_harness(database, UIProvider())
    model_update, conversation_update, active_id, history, status = UIController(
        restarted
    ).bootstrap()

    assert active_id == first["id"]
    assert conversation_update["value"] == first["id"]
    assert model_update["value"] == "fake/original"
    assert history == [
        {"role": "user", "content": "Still here?"},
        {"role": "assistant", "content": "Still here."},
    ]
    assert "Restored conversation" in status


def test_previous_conversations_can_be_browsed_and_resume_pinned_model(tmp_path):
    harness = create_harness(tmp_path / "browse.db", UIProvider())
    older = harness.state.create_conversation("fake/older", provider="fake")
    harness.state.append_message(older["id"], "user", "old message")
    newer = harness.state.create_conversation("fake/newer", provider="fake")

    active_id, history, model_update, _status = UIController(
        harness
    ).select_conversation(older["id"])

    assert active_id == older["id"]
    assert history == [{"role": "user", "content": "old message"}]
    assert model_update["value"] == "fake/older"
    assert harness.state.active_conversation_id() == older["id"]
    assert harness.state.get_conversation(newer["id"])["model"] == "fake/newer"


def test_selected_model_survives_restart_before_first_conversation(tmp_path):
    database = tmp_path / "model.db"
    first = create_harness(database, UIProvider())
    UIController(first).select_model("fake/chosen", None)

    restarted = create_harness(database, UIProvider())
    model_update, _browser, active_id, history, _status = UIController(
        restarted
    ).bootstrap()

    assert active_id is None
    assert history == []
    assert model_update["value"] == "fake/chosen"


def test_gradio_interface_builds_without_network_or_key(tmp_path):
    harness = create_harness(tmp_path / "ui.db", UIProvider())
    interface = build_interface(harness)
    assert interface is not None


def test_ui_shows_provider_failure_without_adding_an_assistant_message(tmp_path):
    @dataclass
    class FailingUIProvider(UIProvider):
        def complete(self, _request):
            raise ProviderError(
                "gateway unavailable",
                ProviderDiagnostics(http_status=502),
            )

    harness = create_harness(tmp_path / "failure.db", FailingUIProvider())
    controller = UIController(harness)
    conversation_id, _browser, history, _model, _status = controller.new_conversation(
        "fake/medium"
    )
    _, staged, active_id, pending, _browser, _status = controller.stage_message(
        "Hello", history, conversation_id, "fake/medium"
    )

    rendered, pending, status = controller.complete_message(pending, staged, active_id)

    assert pending is None
    assert rendered == [{"role": "user", "content": "Hello"}]
    assert "failed with ProviderError: gateway unavailable" in status
    assert harness.state.messages(conversation_id) == rendered


def test_unified_cli_has_run_and_init_commands():
    result = CliRunner().invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "run" in result.stdout
    assert "init" in result.stdout
