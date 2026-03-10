"""RAG chatbot page."""
import os
from nicegui import app, ui, run
from config import AppConfig, get_models_dir


def rag_page():
    config = AppConfig()
    rag_state = {"system": None, "initialized": False, "chat_messages": None}

    # Prevent the Quasar QPage from scrolling
    ui.query(".q-page").style("overflow: hidden")

    ui.label("RAG Chat").classes("text-h4")
    ui.label("Chat with your documents using Qwen AI").classes("text-subtitle1")
    ui.separator()

    @ui.refreshable
    def content():
        if not rag_state["initialized"]:
            _setup_ui()
        else:
            _chat_ui()

    def _setup_ui():
        from RAG.hardware import detect_hardware
        hw_info = detect_hardware()

        # Migration notice for existing Llama users
        saved_model = config.get("defaults.rag_model_path", "")
        if saved_model and "llama" in os.path.basename(saved_model).lower():
            config.set("defaults.rag_model_path", "")
            config.save()
            ui.notify(
                "MDMT now uses Qwen 3.5 models for improved quality. "
                "Please download a Qwen model from the Downloads page.",
                type="info",
                timeout=10000,
            )

        with ui.card().classes("w-full"):
            doc_dir = ui.input("Documents Directory").classes("w-full")
            ui.button("Browse...", on_click=lambda: _browse_dir(doc_dir), icon="folder_open").props("flat")

            # Hardware info
            hw_text = (
                f"{hw_info.gpu_type.upper()} GPU — {hw_info.vram_mb} MB VRAM"
                if hw_info.gpu_available
                else f"No GPU — {hw_info.ram_mb} MB RAM"
            )
            ui.label(f"Detected hardware: {hw_text}").classes("text-caption")

            # Model selector — dropdown of downloaded .gguf files + Browse option
            models_dir = get_models_dir()
            gguf_files = sorted(
                [f for f in os.listdir(models_dir) if f.endswith(".gguf")]
            ) if os.path.isdir(models_dir) else []

            saved_path = config.get("defaults.rag_model_path", "")
            default_model = None
            if saved_path and os.path.exists(saved_path):
                default_model = saved_path
            elif gguf_files:
                # Try to pick the recommended model, else first available
                rec_tag = hw_info.recommended_model  # e.g. "0.8B", "2B", "4B"
                for f in gguf_files:
                    if f"-{rec_tag}-" in f or f"-{rec_tag}." in f:
                        default_model = os.path.join(models_dir, f)
                        break
                if not default_model:
                    default_model = os.path.join(models_dir, gguf_files[0])

            model_options = {os.path.join(models_dir, f): f for f in gguf_files}
            model_select = ui.select(
                options=model_options,
                value=default_model,
                label="Model File (.gguf)",
            ).classes("w-full")

            model_path_input = ui.input(
                "Or enter custom model path",
                value="" if default_model else config.get("defaults.rag_model_path", ""),
            ).classes("w-full")
            ui.button("Browse...", on_click=lambda: _browse_file(model_path_input), icon="folder_open").props("flat")

            if not gguf_files:
                ui.label("No models found. Visit the Downloads page to get a Qwen model.").classes("text-warning")

            # Context length
            ctx_length = ui.number(
                "Context Length",
                value=config.get("defaults.rag_context_window", 32768),
                min=2048,
                max=65536,
                step=1024,
            ).classes("w-48").tooltip(
                "Higher values improve reasoning but use more memory. Range: 2048-65536"
            )

            # Thinking mode toggle
            thinking = ui.switch(
                "Enable thinking mode",
                value=config.get("defaults.rag_thinking_mode", False),
            ).tooltip("Enable chain-of-thought reasoning (slower but higher quality)")

            status_label = ui.label("Not initialized")
            progress = ui.linear_progress(show_value=False).props("indeterminate").classes("w-full")
            progress.set_visibility(False)

            async def initialize():
                if not doc_dir.value:
                    ui.notify("Please select a documents directory.", type="warning")
                    return

                # Resolve model path: prefer dropdown, fall back to custom input
                chosen_model = model_select.value or model_path_input.value
                if not chosen_model or not os.path.exists(chosen_model):
                    ui.notify("Please select a valid model file.", type="warning")
                    return

                ctx_val = ctx_length.value
                if ctx_val is None:
                    ui.notify("Please enter a context length.", type="warning")
                    return
                ctx_val = int(ctx_val)

                progress.set_visibility(True)
                status_label.set_text("Loading model and indexing documents...")

                def do_init():
                    from RAG.qwen_rag import QwenRAGSystem
                    return QwenRAGSystem(
                        documents_dir=doc_dir.value,
                        llm_model_path=chosen_model,
                        context_window=ctx_val,
                        enable_thinking=thinking.value,
                        n_gpu_layers=hw_info.n_gpu_layers,
                        verbose=False,
                    )

                try:
                    rag_state["system"] = await run.io_bound(do_init)
                    rag_state["initialized"] = True
                    config.set("defaults.rag_model_path", chosen_model)
                    config.set("defaults.rag_context_window", ctx_val)
                    config.set("defaults.rag_thinking_mode", thinking.value)
                    config.save()
                    content.refresh()
                except Exception as e:
                    status_label.set_text(f"Error: {e}")
                    progress.set_visibility(False)
                    ui.notify(f"Failed to initialize RAG: {e}", type="negative")

            ui.button("Initialize RAG", on_click=initialize, icon="play_arrow").props("color=primary")

    def _chat_ui():
        # Self-contained flex column with its own height constraint.
        # This avoids needing flex to chain through the refreshable container.
        with ui.column().classes("w-full").style(
            "height: calc(100vh - 165px); overflow: hidden"
        ):
            chat_messages = ui.column().classes("w-full").style(
                "flex: 1; min-height: 0; overflow-y: auto; padding: 8px"
            )
            rag_state["chat_messages"] = chat_messages

            with chat_messages:
                ui.chat_message(
                    "Hello! I've indexed your documents. Ask me anything about them.",
                    name="Assistant",
                    stamp="System",
                ).props("bg-color=blue-2")

            with ui.row().classes("w-full items-center q-mt-sm").style("flex-shrink: 0"):
                message_input = ui.input(placeholder="Type your question...").classes("flex-grow")
                send_btn = ui.button("Send", icon="send").props("color=primary")

        async def send_message():
            question = message_input.value
            if not question:
                return

            message_input.set_value("")
            with chat_messages:
                ui.chat_message(question, name="You", sent=True)
                thinking = ui.chat_message("Thinking...", name="Assistant").props("bg-color=blue-2")

            send_btn.disable()

            def do_query():
                return rag_state["system"].query(question)

            try:
                result = await run.io_bound(do_query)
                chat_messages.remove(thinking)

                answer = result["answer"]
                sources_text = ""
                if result.get("sources"):
                    unique = {}
                    for s in result["sources"]:
                        key = os.path.basename(s["source"])
                        if s.get("page") is not None:
                            key += f" (p.{s['page']})"
                        unique[key] = True
                    sources_text = "\n\nSources: " + ", ".join(unique.keys())

                with chat_messages:
                    ui.chat_message(
                        answer + sources_text,
                        name="Assistant",
                        stamp=f"{result.get('processing_time', 0):.1f}s",
                    ).props("bg-color=blue-2")
            except Exception as e:
                chat_messages.remove(thinking)
                with chat_messages:
                    ui.chat_message(f"Error: {e}", name="Assistant").props("bg-color=red-2")
            finally:
                send_btn.enable()

        send_btn.on_click(send_message)
        message_input.on("keydown.enter", send_message)

    content()


async def _browse_dir(target_input):
    import webview
    result = await app.native.main_window.create_file_dialog(
        dialog_type=webview.FileDialog.FOLDER,
        allow_multiple=False,
    )
    if result and len(result) > 0:
        target_input.set_value(result[0])


async def _browse_file(target_input):
    import webview
    result = await app.native.main_window.create_file_dialog(
        dialog_type=webview.FileDialog.OPEN,
        allow_multiple=False,
        file_types=("GGUF Models (*.gguf)",),
    )
    if result and len(result) > 0:
        target_input.set_value(result[0])
