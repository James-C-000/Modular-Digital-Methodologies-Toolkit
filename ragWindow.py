#!/usr/bin/python3
import os
import tkinter as tk
from tkinter import ttk
import pygubu
import threading
import subprocess
import sys

PROJECT_PATH = os.getcwd()
PROJECT_UI = os.path.join(PROJECT_PATH, 'ragWindow.ui')
DEFAULT_MODEL_PATH = os.path.join(PROJECT_PATH, 'RAG', 'models', 'Llama-3.2-3B-Instruct-Q5_K_M.gguf')


class ragWindow:
    def __init__(self, master=None):
        self.builder = builder = pygubu.Builder()
        builder.add_resource_path(PROJECT_PATH)
        builder.add_from_file(PROJECT_UI)
        # Main widget
        self.mainwindow: tk.Toplevel = builder.get_object("ragWindow", master)
        # Create dialog references
        self.aboutDialog = builder.get_object("aboutDialog", self.mainwindow)
        self.licenseDialog = builder.get_object("licenseDialog", self.mainwindow)
        self.helpDialog = builder.get_object("helpDialog", self.mainwindow)
        # Get UI elements
        self.documentDir = builder.get_object("documentInputDir", self.mainwindow)
        self.modelPath = builder.get_object("modelPathInput", self.mainwindow)
        self.runRagButton = builder.get_object("button_run_rag", self.mainwindow)
        # Set default model path if it exists
        if os.path.exists(DEFAULT_MODEL_PATH):
            self.modelPath.configure(path=DEFAULT_MODEL_PATH)
        # Main menu
        _main_menu = builder.get_object("menuBar", self.mainwindow)
        self.mainwindow.configure(menu=_main_menu)
        builder.connect_callbacks(self)

    def on_run_rag_clicked(self):
        # Get user input vars
        docDir = self.documentDir.cget('path')
        modelPath = self.modelPath.cget('path')

        if not docDir:
            tk.messagebox.showerror("Error", "Please select a documents directory.")
            return

        if not modelPath:
            tk.messagebox.showerror("Error", "Please select a Llama model file.")
            return

        # Check if model file exists
        if not os.path.exists(modelPath):
            tk.messagebox.showerror("Error", f"Model file not found: {modelPath}")
            return

        # Disable button immediately before launching RAG
        self.runRagButton.configure(state='disabled')
        self.mainwindow.update()  # Force UI update to show disabled state

        # Launch RAG terminal
        self.launch_rag_terminal(docDir, modelPath)

    def launch_rag_terminal(self, docDir, modelPath):
        terminal_window = None
        rag_system = None

        try:
            # Create a new toplevel window for the RAG terminal
            terminal_window = tk.Toplevel(self.mainwindow)
            terminal_window.title("MDMT RAGbot")
            terminal_window.geometry("800x600")
            terminal_window.minsize(600, 400)

            # Create a frame for the terminal display with scrollbars
            terminal_frame = ttk.Frame(terminal_window)
            terminal_frame.pack(fill='both', expand=True, padx=10, pady=10)

            # Add text widget for output
            output_text = tk.Text(terminal_frame, wrap=tk.WORD, bg='black', fg='white',
                                  font=('Courier', 10))
            output_text.pack(side=tk.TOP, fill='both', expand=True)

            # Add scrollbars
            y_scrollbar = ttk.Scrollbar(output_text, orient='vertical', command=output_text.yview)
            y_scrollbar.pack(side=tk.RIGHT, fill='y')
            output_text.config(yscrollcommand=y_scrollbar.set)

            # Add input frame
            input_frame = ttk.Frame(terminal_window)
            input_frame.pack(fill='x', padx=10, pady=(0, 10))

            # Add prompt label
            prompt_label = ttk.Label(input_frame, text=">>> ")
            prompt_label.pack(side=tk.LEFT)

            # Add input entry
            input_entry = ttk.Entry(input_frame, width=50)
            input_entry.pack(side=tk.LEFT, fill='x', expand=True, padx=(0, 5))
            input_entry.focus_set()  # Set focus to the entry widget

            # Add send button
            send_button = ttk.Button(input_frame, text="Send")
            send_button.pack(side=tk.RIGHT)

            # Initialize the RAG system
            from RAG.llama32_rag import Llama32RAGSystem
            import sys
            import io

            # Custom stdout to capture output
            class StdoutRedirector(io.StringIO):
                def __init__(self, text_widget):
                    super().__init__()
                    self.text_widget = text_widget

                def write(self, string):
                    self.text_widget.config(state=tk.NORMAL)
                    self.text_widget.insert(tk.END, string)
                    self.text_widget.see(tk.END)  # Scroll to the end
                    self.text_widget.config(state=tk.DISABLED)

                def flush(self):
                    pass

            # Progress indicator for initialization
            output_text.config(state=tk.NORMAL)
            output_text.insert(tk.END, f"Initializing Llama-3.2 RAG system...\n")
            output_text.insert(tk.END, f"Documents directory: {docDir}\n")
            output_text.insert(tk.END, f"Model: {os.path.basename(modelPath)}\n")
            output_text.insert(tk.END, f"Please wait while the model loads...\n\n")
            output_text.config(state=tk.DISABLED)
            terminal_window.update()

            # Initialize RAG system in a separate thread to avoid freezing the GUI
            rag_ready = threading.Event()

            def initialize_rag():
                nonlocal rag_system
                try:
                    # Redirect stdout to our text widget during initialization
                    old_stdout = sys.stdout
                    sys.stdout = StdoutRedirector(output_text)

                    # Initialize RAG system (this might take some time)
                    rag_system = Llama32RAGSystem(
                        documents_dir=docDir,
                        llm_model_path=modelPath,
                        verbose=True
                    )

                    # Restore stdout
                    sys.stdout = old_stdout

                    # Signal that RAG is ready
                    rag_ready.set()

                    # Update UI in the main thread
                    if terminal_window and terminal_window.winfo_exists():
                        terminal_window.after(0, lambda: display_ready_message())

                except Exception as e:
                    sys.stdout = old_stdout
                    error_msg = f"Error initializing RAG system: {str(e)}\n"
                    if terminal_window and terminal_window.winfo_exists():
                        terminal_window.after(0, lambda: display_error(error_msg))

            def display_ready_message():
                if not terminal_window or not terminal_window.winfo_exists():
                    return

                output_text.config(state=tk.NORMAL)
                output_text.insert(tk.END, "\n====================================\n")
                output_text.insert(tk.END, "RAG system initialized and ready!\n")
                output_text.insert(tk.END, "Type your question below and press Enter or click Send.\n")
                output_text.insert(tk.END, "Type 'exit' to close the terminal.\n")
                output_text.insert(tk.END, "====================================\n\n")
                output_text.config(state=tk.DISABLED)
                input_entry.config(state=tk.NORMAL)
                send_button.config(state=tk.NORMAL)

            def display_error(error_msg):
                if not terminal_window or not terminal_window.winfo_exists():
                    return

                output_text.config(state=tk.NORMAL)
                output_text.insert(tk.END, "\n====================================\n")
                output_text.insert(tk.END, error_msg)
                output_text.insert(tk.END, "\nPlease check your settings and try again.\n")
                output_text.insert(tk.END, "====================================\n\n")
                output_text.config(state=tk.DISABLED)

            # Store the initialization thread to manage graceful shutdown
            init_thread = threading.Thread(target=initialize_rag, daemon=True)
            init_thread.start()

            # Disable input until initialization is complete
            input_entry.config(state=tk.DISABLED)
            send_button.config(state=tk.DISABLED)

            # Function to process user input
            def process_input(event=None):
                if not terminal_window or not terminal_window.winfo_exists():
                    return

                user_input = input_entry.get().strip()

                if not user_input:
                    return

                # Clear the input field
                input_entry.delete(0, tk.END)

                # Display user input
                output_text.config(state=tk.NORMAL)
                output_text.insert(tk.END, f"\nYou: {user_input}\n\n")
                output_text.config(state=tk.DISABLED)

                # Check for exit command
                if user_input.lower() == 'exit':
                    terminal_window.destroy()
                    return

                # Disable input while processing
                input_entry.config(state=tk.DISABLED)
                send_button.config(state=tk.DISABLED)

                # Process the query in a separate thread
                def query_rag():
                    try:
                        if not terminal_window or not terminal_window.winfo_exists() or not rag_system:
                            return

                        # Redirect stdout
                        old_stdout = sys.stdout
                        sys.stdout = StdoutRedirector(output_text)

                        # Process query
                        if terminal_window and terminal_window.winfo_exists():
                            output_text.config(state=tk.NORMAL)
                            output_text.insert(tk.END, "Thinking...\n\n")
                            output_text.config(state=tk.DISABLED)

                        result = rag_system.query(user_input)

                        # Display result
                        if terminal_window and terminal_window.winfo_exists():
                            output_text.config(state=tk.NORMAL)
                            output_text.insert(tk.END, f"Assistant: {result['answer']}\n\n")

                            # Display sources if available
                            if result['sources']:
                                output_text.insert(tk.END, "Sources:\n")
                                unique_sources = {}
                                for source in result['sources']:
                                    source_text = os.path.basename(source['source'])
                                    if source.get('page') is not None:
                                        key = f"{source_text}:{source['page']}"
                                    else:
                                        key = source_text
                                    unique_sources[key] = source

                                for i, (_, source) in enumerate(unique_sources.items(), 1):
                                    source_text = os.path.basename(source['source'])
                                    if source.get('page') is not None:
                                        source_text += f" (page {source['page']})"
                                    output_text.insert(tk.END, f"{i}. {source_text}\n")

                                output_text.insert(tk.END, f"\n(Processed in {result['processing_time']:.2f}s)\n\n")

                            output_text.config(state=tk.DISABLED)

                        # Restore stdout
                        sys.stdout = old_stdout

                    except Exception as e:
                        # Handle error
                        if terminal_window and terminal_window.winfo_exists():
                            output_text.config(state=tk.NORMAL)
                            output_text.insert(tk.END, f"Error: {str(e)}\n\n")
                            output_text.config(state=tk.DISABLED)
                        sys.stdout = old_stdout

                    # Re-enable input if the window still exists
                    if terminal_window and terminal_window.winfo_exists():
                        terminal_window.after(0, lambda: input_entry.config(state=tk.NORMAL))
                        terminal_window.after(0, lambda: send_button.config(state=tk.NORMAL))
                        terminal_window.after(0, lambda: input_entry.focus_set())

                # Start processing in a separate thread
                threading.Thread(target=query_rag, daemon=True).start()

            # Bind the Enter key and send button
            input_entry.bind("<Return>", process_input)
            send_button.config(command=process_input)

            # Handle window close with graceful shutdown
            def on_closing():
                nonlocal rag_system

                # Show a "closing" message
                output_text.config(state=tk.NORMAL)
                output_text.insert(tk.END, "\n====================================\n")
                output_text.insert(tk.END, "Shutting down RAG system...\n")
                output_text.insert(tk.END, "====================================\n\n")
                output_text.config(state=tk.DISABLED)
                terminal_window.update()

                # Clean up resources
                try:
                    # Release any resources held by the RAG system
                    # This is a placeholder - add specific cleanup if needed
                    rag_system = None

                    # Destroy the window
                    terminal_window.destroy()
                finally:
                    # Re-enable the launch button - ensure this happens even if cleanup fails
                    self.runRagButton.configure(state='normal')

            terminal_window.protocol("WM_DELETE_WINDOW", on_closing)

        except Exception as e:
            import tkinter.messagebox as messagebox
            messagebox.showerror("Error", f"Failed to launch RAG terminal: {str(e)}")

            # Clean up if the window was partially created
            if terminal_window and terminal_window.winfo_exists():
                terminal_window.destroy()

            # Re-enable the launch button if there's an error
            self.runRagButton.configure(state='normal')
    def on_quit_item_clicked(self):
        # Quit on exit
        self.mainwindow.destroy()

    def on_about_item_clicked(self):
        # Open the "About MDMT" window
        self.aboutDialog.run()

    def on_help_item_clicked(self):
        self.helpDialog.run()

    def on_viewLicenses_item_clicked(self):
        # Open the license terms text window
        self.licenseDialog.run()

    def run(self):
        self.mainwindow.mainloop()


if __name__ == "__main__":
    app = ragWindow()
    app.run()