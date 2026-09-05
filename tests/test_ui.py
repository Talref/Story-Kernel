from __future__ import annotations

from dataclasses import dataclass, field

from typer.testing import CliRunner

from story_kernel.cli import app
from story_kernel.contracts import ModelInfo, ProviderMessage, ProviderResponse, ToolCall
from story_kernel.ui import UIController, build_interface, create_harness


@dataclass
class UIProvider:
    name: str = "fake"
    responses: list[ProviderResponse] = field(default_factory=list)

    def list_models(self):
        return [ModelInfo(id="fake/medium", name="Medium", capabilities={"tool_calling": True})]

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
    conversation_id, history, _status = controller.new_conversation("fake/medium")

    _, history, active_id, _status = controller.chat(
        "Remember this", history, conversation_id, "fake/other"
    )
    assert active_id == conversation_id
    assert history[-1] == {"role": "assistant", "content": "Stored."}
    assert harness.state.get_conversation(active_id)["model"] == "fake/medium"
    assert harness.state.world_snapshot()["objects"]

    new_id, new_history, _status = controller.new_conversation("fake/medium")
    assert new_id != conversation_id
    assert new_history == []
    assert harness.state.world_snapshot()["objects"]

    controller.reset_world()
    assert harness.state.world_snapshot()["objects"] == []
    assert harness.state.get_conversation(new_id)["model"] == "fake/medium"


def test_gradio_interface_builds_without_network_or_key(tmp_path):
    harness = create_harness(tmp_path / "ui.db", UIProvider())
    interface = build_interface(harness)
    assert interface is not None


def test_unified_cli_has_run_and_init_commands():
    result = CliRunner().invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "run" in result.stdout
    assert "init" in result.stdout

