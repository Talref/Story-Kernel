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
        self._model_choices: dict[str, str] = {}

    def _fetch_models(self) -> tuple[int, str | None]:
        try:
            models = self.harness.provider.list_models()
            self._model_choices = {
                model.id: (model.name or model.id) + f" — {model.id}"
                for model in models
            }
            return len(models), None
        except ProviderError as exc:
            return 0, str(exc)

    def _model_update(self, selected: str | None):
        if selected and selected not in self._model_choices:
            self._model_choices[selected] = f"{selected} — saved"
        choices = [
            (label, model_id)
            for model_id, label in sorted(
                self._model_choices.items(), key=lambda item: item[1].casefold()
            )
        ]
        return gr.update(choices=choices, value=selected)

    def _conversation_update(self, selected: str | None):
        choices = [
            (
                f"{item['created_at'][:19]} · {item['model']} · {item['id'][-8:]}",
                item["id"],
            )
            for item in self.harness.state.list_conversations()
        ]
        return gr.update(choices=choices, value=selected)

    def bootstrap(self):
        count, model_error = self._fetch_models()
        conversations = self.harness.state.list_conversations()
        active_id = self.harness.state.active_conversation_id()
        if active_id is None and conversations:
            active_id = conversations[0]["id"]
            self.harness.state.set_active_conversation(active_id)

        history: list[dict[str, Any]] = []
        selected_model = self.harness.state.selected_model()
        if active_id:
            conversation = self.harness.state.get_conversation(active_id)
            selected_model = conversation["model"]
            history = self.harness.state.messages(active_id)
            status = (
                f"Restored conversation `{active_id}` pinned to `{selected_model}` "
                f"with {len(history)} messages."
            )
        else:
            status = "No previous conversation. Select a model to begin."
        if model_error:
            status += f" Model refresh failed: {model_error}"
        else:
            status += f" Loaded {count} subscription models."
        return (
            self._model_update(selected_model),
            self._conversation_update(active_id),
            active_id,
            history,
            status,
        )

    def refresh_models(self, current: str | None = None):
        count, error = self._fetch_models()
        selected = current or self.harness.state.selected_model()
        if selected is None and self._model_choices:
            selected = next(iter(self._model_choices))
            self.harness.state.set_selected_model(selected)
        if error:
            return self._model_update(selected), error
        return self._model_update(selected), f"Loaded {count} subscription models."

    def select_model(self, model: str | None, conversation_id: str | None):
        self.harness.state.set_selected_model(model)
        if conversation_id:
            pinned = self.harness.state.get_conversation(conversation_id)["model"]
            return f"Selected `{model}` for the next conversation. Current conversation remains pinned to `{pinned}`."
        return f"Selected `{model}` for the next conversation."

    def new_conversation(self, model: str | None):
        if not model:
            return (
                None,
                self._conversation_update(None),
                [],
                self._model_update(None),
                "Select a model first.",
            )
        conversation = self.harness.state.create_conversation(
            model, provider=self.harness.provider.name
        )
        return (
            conversation["id"],
            self._conversation_update(conversation["id"]),
            [],
            self._model_update(model),
            f"New conversation pinned to `{model}`. World state was preserved.",
        )

    def select_conversation(self, conversation_id: str | None):
        if not conversation_id:
            self.harness.state.set_active_conversation(None)
            selected = self.harness.state.selected_model()
            return None, [], self._model_update(selected), "No conversation selected."
        conversation = self.harness.state.get_conversation(conversation_id)
        self.harness.state.set_active_conversation(conversation_id)
        self.harness.state.set_selected_model(conversation["model"])
        history = self.harness.state.messages(conversation_id)
        return (
            conversation_id,
            history,
            self._model_update(conversation["model"]),
            f"Opened conversation `{conversation_id}` pinned to `{conversation['model']}`.",
        )

    def stage_message(
        self,
        message: str,
        history: list[dict[str, Any]] | None,
        conversation_id: str | None,
        selected_model: str | None,
    ):
        existing = list(history or [])
        if not message.strip():
            return (
                message,
                existing,
                conversation_id,
                None,
                self._conversation_update(conversation_id),
                "Enter a message.",
            )
        if conversation_id is None:
            if not selected_model:
                return (
                    message,
                    existing,
                    None,
                    None,
                    self._conversation_update(None),
                    "Select a model first.",
                )
            conversation = self.harness.state.create_conversation(
                selected_model, provider=self.harness.provider.name
            )
            conversation_id = conversation["id"]
        pinned = self.harness.state.get_conversation(conversation_id)["model"]
        self.harness.state.set_active_conversation(conversation_id)
        safe_message = self.harness.sanitize(message)
        existing.append({"role": "user", "content": safe_message})
        return (
            "",
            existing,
            conversation_id,
            safe_message,
            self._conversation_update(conversation_id),
            f"Sending with conversation model `{pinned}`…",
        )

    def complete_message(
        self,
        pending_message: str | None,
        history: list[dict[str, Any]] | None,
        conversation_id: str | None,
    ):
        existing = list(history or [])
        if not pending_message or not conversation_id:
            return existing, None, "No message was sent."
        pinned = self.harness.state.get_conversation(conversation_id)["model"]
        result = self.harness.runtime.run_turn(conversation_id, pending_message)
        existing.append({"role": "assistant", "content": result["assistant_response"]})
        status = f"Conversation `{conversation_id}` · pinned `{pinned}` · execution `{result['execution_id']}`"
        return existing, None, status

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
            return human, raw, "Import committed. Restoring imported UI state."
        except (ValueError, TypeError) as exc:
            human, raw = self.world_views()
            return human, raw, f"Import rejected: {exc}"


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
        pending_message = gr.State(value=None)

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
        conversation_browser = gr.Dropdown(
            choices=[],
            label="Previous conversations",
            info="Select a persisted conversation to restore and resume it.",
            filterable=True,
            interactive=True,
        )
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

        demo.load(
            controller.bootstrap,
            outputs=[model, conversation_browser, conversation_id, chat, status],
        ).then(controller.trace_view, [conversation_id], [trace])
        refresh_models.click(controller.refresh_models, [model], [model, status])
        model.input(controller.select_model, [model, conversation_id], [status])
        new_conversation.click(
            controller.new_conversation,
            [model],
            [conversation_id, conversation_browser, chat, model, status],
        ).then(controller.trace_view, [conversation_id], [trace])
        conversation_browser.input(
            controller.select_conversation,
            [conversation_browser],
            [conversation_id, chat, model, status],
        ).then(controller.trace_view, [conversation_id], [trace])

        staged_send = send.click(
            controller.stage_message,
            [message, chat, conversation_id, model],
            [
                message,
                chat,
                conversation_id,
                pending_message,
                conversation_browser,
                status,
            ],
        )
        staged_send.then(
            controller.complete_message,
            [pending_message, chat, conversation_id],
            [chat, pending_message, status],
        ).then(controller.world_views, outputs=[readable, raw]).then(
            controller.trace_view, [conversation_id], [trace]
        )

        staged_submit = message.submit(
            controller.stage_message,
            [message, chat, conversation_id, model],
            [
                message,
                chat,
                conversation_id,
                pending_message,
                conversation_browser,
                status,
            ],
        )
        staged_submit.then(
            controller.complete_message,
            [pending_message, chat, conversation_id],
            [chat, pending_message, status],
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
            [readable, raw, status],
        ).then(
            controller.bootstrap,
            outputs=[model, conversation_browser, conversation_id, chat, status],
        ).then(controller.trace_view, [conversation_id], [trace])

    return demo
