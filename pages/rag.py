"""RAG chatbot page."""
import os
from nicegui import app, ui, run
from config import AppConfig, get_models_dir


def rag_page():
    config = AppConfig()
    rag_state = {"system": None, "initialized": False}

    ui.label("RAG Chat").classes("text-h4")
    ui.label("Chat with your documents using Llama AI").classes("text-subtitle1")
    ui.separator()

    with ui.card().classes("w-full") as setup_card:
        doc_dir = ui.input("Documents Directory").classes("w-full")
        ui.button("Browse...", on_click=lambda: _browse_dir(doc_dir), icon="folder_open").props("flat")

        model_path = ui.input(
            "Model File (.gguf)",
            value=config.get("defaults.rag_model_path", ""),
        ).classes("w-full")
        ui.button("Browse...", on_click=lambda: _browse_file(model_path), icon="folder_open").props("flat")

        init_status = ui.label("Not initialized")
        init_progress = ui.linear_progress(value=0).classes("w-full")
        init_progress.set_visibility(False)

    chat_container = ui.column().classes("w-full")
    chat_container.set_visibility(False)

    async def initialize_rag():
        if not doc_dir.value:
            ui.notify("Please select a documents directory.", type="warning")
            return
        if not model_path.value or not os.path.exists(model_path.value):
            ui.notify("Please select a valid model file.", type="warning")
            return

        init_progress.set_visibility(True)
        init_status.set_text("Loading model and indexing documents...")

        def do_init():
            from RAG.llama32_rag import Llama32RAGSystem
            return Llama32RAGSystem(
                documents_dir=doc_dir.value,
                llm_model_path=model_path.value,
                verbose=False,
            )

        try:
            rag_state["system"] = await run.io_bound(do_init)
            rag_state["initialized"] = True
            init_status.set_text("RAG system ready!")
            init_progress.set_visibility(False)
            setup_card.set_visibility(False)
            chat_container.set_visibility(True)

            with chat_container:
                ui.chat_message(
                    "Hello! I've indexed your documents. Ask me anything about them.",
                    name="Assistant",
                    stamp="System",
                ).props("bg-color=blue-2")

                message_input = ui.input(placeholder="Type your question...").classes("w-full")
                send_btn = ui.button("Send", icon="send").props("color=primary")

                async def send_message():
                    question = message_input.value
                    if not question:
                        return

                    message_input.set_value("")
                    ui.chat_message(question, name="You", sent=True)

                    send_btn.disable()
                    thinking = ui.chat_message("Thinking...", name="Assistant").props("bg-color=blue-2")

                    def do_query():
                        return rag_state["system"].query(question)

                    try:
                        result = await run.io_bound(do_query)
                        chat_container.remove(thinking)

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

                        ui.chat_message(
                            answer + sources_text,
                            name="Assistant",
                            stamp=f"{result.get('processing_time', 0):.1f}s",
                        ).props("bg-color=blue-2")
                    except Exception as e:
                        chat_container.remove(thinking)
                        ui.chat_message(f"Error: {e}", name="Assistant").props("bg-color=red-2")
                    finally:
                        send_btn.enable()

                send_btn.on_click(send_message)
                message_input.on("keydown.enter", send_message)

            config.set("defaults.rag_model_path", model_path.value)
            config.set("last_page", "/rag")
            config.save()

        except Exception as e:
            init_status.set_text(f"Error: {e}")
            init_progress.set_visibility(False)
            ui.notify(f"Failed to initialize RAG: {e}", type="negative")

    ui.button("Initialize RAG", on_click=initialize_rag, icon="play_arrow").props("color=primary")


async def _browse_dir(target_input):
    import webview
    result = await app.native.main_window.create_file_dialog(
        dialog_type=webview.FOLDER_DIALOG,
        allow_multiple=False,
    )
    if result and len(result) > 0:
        target_input.set_value(result[0])


async def _browse_file(target_input):
    import webview
    result = await app.native.main_window.create_file_dialog(
        dialog_type=webview.OPEN_DIALOG,
        allow_multiple=False,
        file_types=("GGUF Models (*.gguf)",),
    )
    if result and len(result) > 0:
        target_input.set_value(result[0])
