"""Co-word analysis page."""
import os
from nicegui import ui, run
from pages.pickers import browse_dir
from config import AppConfig


def cowords_page():
    config = AppConfig()

    ui.label("Co-Word Analysis").classes("text-h4")
    ui.label("Generate word co-occurrence networks to reveal conceptual relationships").classes("text-subtitle1")
    ui.separator()

    from NLP.text_utils import STOPWORD_LANGUAGES, parse_custom_stopwords

    with ui.card().classes("w-full"):
        input_dir = ui.input("Input Directory", value=config.get("defaults.cowords_input_dir", "")).classes("w-full")
        ui.button("Browse...", on_click=lambda: browse_dir(input_dir), icon="folder_open").props("flat")

    with ui.card().classes("w-full"):
        stop_options = {"": "None (keep every word)"}
        stop_options.update({code: f"{name} \u2014 {source}" for code, (name, source) in STOPWORD_LANGUAGES.items()})
        stop_lang = ui.select(
            stop_options, label="Stopword list (words to ignore)", with_input=True,
            value=config.get("defaults.cowords_stopwords", "en"),
        ).classes("w-full")
        ui.label(
            "Snowball lists contain only function words (the, and, of...). \"Extended\" lists, used for"
            " languages Snowball does not cover, are broader and may remove some content words."
        ).classes("text-caption text-grey")
        custom_stops = ui.textarea(
            "Additional words to ignore (optional)",
            value=config.get("defaults.cowords_custom_stopwords", ""),
        ).classes("w-full").props("rows=2")

    progress = ui.linear_progress(show_value=False).props("indeterminate").classes("w-full")
    progress.set_visibility(False)
    status_label = ui.label("Ready")

    async def run_coword():
        in_dir = input_dir.value
        if not in_dir or not os.path.isdir(in_dir):
            ui.notify("Please select a valid input directory.", type="warning")
            return

        progress.set_visibility(True)
        status_label.set_text("Running co-word analysis...")

        try:
            lang = stop_lang.value or None
            extra = parse_custom_stopwords(custom_stops.value)

            def do_coword():
                from NLP.co_word_analysis import main as co_word_main
                co_word_main(in_dir, stopword_language=lang, extra_stopwords=extra)

            await run.io_bound(do_coword)
            status_label.set_text("Co-word analysis complete! Results saved in input directory.")
            ui.notify("Co-word analysis complete!", type="positive")

            summary = os.path.join(in_dir, "Co_Word_Analysis_Summary.html")
            if os.path.exists(summary):
                ui.label("Summary report generated.").classes("text-positive")
        except ImportError as e:
            status_label.set_text(f"Missing dependency: {e}")
            ui.notify(f"Missing dependency: {e}", type="negative")
        except Exception as e:
            status_label.set_text(f"Error: {e}")
            ui.notify(f"Co-word analysis error: {e}", type="negative")
        finally:
            progress.set_visibility(False)

        config.set("defaults.cowords_input_dir", in_dir)
        config.set("defaults.cowords_stopwords", stop_lang.value)
        config.set("defaults.cowords_custom_stopwords", custom_stops.value or "")
        config.set("last_page", "/cowords")
        config.save()

    ui.button("Run Analysis", on_click=run_coword, icon="play_arrow").props("color=primary")
