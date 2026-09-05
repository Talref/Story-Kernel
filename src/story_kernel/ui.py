"""Minimal Gradio inspection surface for Experiment 0.1a."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import gradio as gr

from .capabilities import CapabilityService
from .contracts import ExecutionContext
from .database import create_database
from .exporting import ExperimentSerializer, redact
from .provider import ModelProvider, NanoGPTAdapter, ProviderError
from .runtime import KernelRuntime
from .state import StateStore


@dataclass
class Harness:
    capabilities: CapabilityService
    state: StateStore
    provider: ModelProvider
    runtime: KernelRuntime
    serializer: ExperimentSerializer
    sanitize: Callable[[Any], Any]


def create_harness(
    database_path: str | Path, provider: ModelProvider | None = None
) -> Harness:
    _engine, sessions = create_database(database_path)
    state = StateStore(sessions)
    state.initialize()
    capabilities = CapabilityService(sessions)
    selected_provider = provider or NanoGPTAdapter.from_env()
    # The secret is read again only for export redaction; it is never serialized or put in UI state.
    import os

    secret = (
        os.getenv("NANOGPT_API_KEY", "") if selected_provider.name == "nanogpt" else ""
    )
    sanitize = lambda value: redact(value, (secret,))
    runtime = KernelRuntime(capabilities, state, selected_provider, sanitizer=sanitize)
    serializer = ExperimentSerializer(sessions, known_secrets=(secret,))
    return Harness(
        capabilities, state, selected_provider, runtime, serializer, sanitize
    )


class UIController:
    """Plain callback controller, kept testable without starting an HTTP server."""

    def __init__(self, harness: Harness):
        self.harness = harness

    def refresh_models(self, current: str | None = None):
        try:
            models = self.harness.provider.list_models()
            choices = [
                ((model.name or model.id) + f" — {model.id}", model.id)
                for model in models
            ]
            ids = [model.id for model in models]
            selected = current if current in ids else (ids[0] if ids else None)
            return gr.update(
                choices=choices, value=selected
            ), f"Loaded {len(models)} subscription models."
        except ProviderError as exc:
            return gr.update(choices=[], value=None), str(exc)

    def new_conversation(self, model: str | None):
        if not model:
            return None, [], "Select a model first."
        conversation = self.harness.state.create_conversation(
            model, provider=self.harness.provider.name
        )
        return (
            conversation["id"],
            [],
            f"New conversation pinned to `{model}`. World state was preserved.",
        )

    def chat(
        self,
        message: str,
        history: list[dict[str, Any]] | None,
        conversation_id: str | None,
        selected_model: str | None,
    ):
        existing = list(history or [])
        if not message.strip():
            return "", existing, conversation_id, "Enter a message."
        if conversation_id is None:
            if not selected_model:
                return message, existing, None, "Select a model first."
            conversation = self.harness.state.create_conversation(
                selected_model, provider=self.harness.provider.name
            )
            conversation_id = conversation["id"]
        pinned = self.harness.state.get_conversation(conversation_id)["model"]
        result = self.harness.runtime.run_turn(conversation_id, message)
        existing.extend(
            [
                {"role": "user", "content": message},
                {"role": "assistant", "content": result["assistant_response"]},
            ]
        )
        status = f"Conversation `{conversation_id}` · pinned `{pinned}` · execution `{result['execution_id']}`"
        return "", existing, conversation_id, status

    def save_prompt(self, content: str):
        try:
            version, saved = self.harness.state.save_prompt(
                self.harness.sanitize(content)
            )
            return saved, f"Saved application prompt version {version}."
        except ValueError as exc:
            return content, str(exc)

    def world_views(self):
        snapshot = self.harness.sanitize(
            self.harness.state.world_snapshot(ExecutionContext())
        )
        human = self.harness.sanitize(self.harness.state.human_world())
        return human, json.dumps(snapshot, indent=2, ensure_ascii=False)

    def trace_view(self, conversation_id: str | None):
        return json.dumps(
            self.harness.sanitize(self.harness.state.executions(conversation_id)),
            indent=2,
            ensure_ascii=False,
            default=str,
        )

    def reset_world(self):
        self.harness.state.reset_world()
        human, raw = self.world_views()
        return (
            human,
            raw,
            "World reset to revision 0. Conversations and prompt were preserved.",
        )

    def export_data(self):
        return self.harness.serializer.export_json(), "Export refreshed."

    def import_data(self, document: str):
        try:
            self.harness.serializer.import_json(document)
            human, raw = self.world_views()
            return (
                human,
                raw,
                None,
                [],
                "Import committed. Start or select a new conversation.",
            )
        except (ValueError, TypeError) as exc:
            human, raw = self.world_views()
            return human, raw, None, [], f"Import rejected: {exc}"


def build_interface(harness: Harness) -> gr.Blocks:
    controller = UIController(harness)
    prompt_version, prompt_content = harness.state.current_prompt()
    prompt_content = harness.sanitize(prompt_content)
    human_world, raw_world = controller.world_views()

    with gr.Blocks(title="Story Kernel · Experiment 0.1a") as demo:
        gr.Markdown(
            "# Story Kernel · Experiment 0.1a\nA sterile A/B/C interaction and inspection harness."
        )
        conversation_id = gr.State(value=None)

        with gr.Row():
            model = gr.Dropdown(
                choices=[],
                label="NanoGPT subscription model",
                info="Selection is pinned when a conversation starts.",
                filterable=True,
                interactive=True,
            )
            refresh_models = gr.Button("Refresh models")
            new_conversation = gr.Button("New conversation", variant="primary")
            reset_world = gr.Button("Reset world", variant="stop")
        status = gr.Markdown("Load models, then start a conversation.")

        with gr.Tab("Chat"):
            chat = gr.Chatbot(label="Conversation", height=480)
            message = gr.Textbox(
                label="Message",
                placeholder="Tell or ask the model something about the world",
            )
            send = gr.Button("Send", variant="primary")

        with gr.Tab("Application contract"):
            prompt = gr.Textbox(
                value=prompt_content,
                label=f"B/application prompt · current version {prompt_version}",
                lines=12,
            )
            save_prompt = gr.Button("Save prompt")

        with gr.Tab("World inspector"):
            refresh_world = gr.Button("Refresh world")
            with gr.Row():
                readable = gr.Markdown(human_world)
                raw = gr.Code(
                    value=raw_world, language="json", label="Raw structured world"
                )

        with gr.Tab("Execution trace"):
            refresh_trace = gr.Button("Refresh trace")
            trace = gr.Code(value="[]", language="json", label="Execution/tool trace")

        with gr.Tab("Import / export"):
            export_button = gr.Button("Export all experiment artifacts")
            export_document = gr.Code(language="json", label="Export JSON")
            import_document = gr.Code(language="json", label="Import JSON")
            import_button = gr.Button("Validate and import", variant="primary")

        demo.load(controller.refresh_models, [model], [model, status])
        refresh_models.click(controller.refresh_models, [model], [model, status])
        new_conversation.click(
            controller.new_conversation,
            [model],
            [conversation_id, chat, status],
        )
        send.click(
            controller.chat,
            [message, chat, conversation_id, model],
            [message, chat, conversation_id, status],
        ).then(controller.world_views, outputs=[readable, raw]).then(
            controller.trace_view, [conversation_id], [trace]
        )
        message.submit(
            controller.chat,
            [message, chat, conversation_id, model],
            [message, chat, conversation_id, status],
        ).then(controller.world_views, outputs=[readable, raw]).then(
            controller.trace_view, [conversation_id], [trace]
        )
        save_prompt.click(controller.save_prompt, [prompt], [prompt, status])
        refresh_world.click(controller.world_views, outputs=[readable, raw])
        refresh_trace.click(controller.trace_view, [conversation_id], [trace])
        reset_world.click(controller.reset_world, outputs=[readable, raw, status])
        export_button.click(controller.export_data, outputs=[export_document, status])
        import_button.click(
            controller.import_data,
            [import_document],
            [readable, raw, conversation_id, chat, status],
        ).then(controller.trace_view, [conversation_id], [trace])

    return demo
