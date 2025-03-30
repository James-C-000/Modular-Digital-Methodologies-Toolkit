# This script takes a directory of audio files and creates a text transcription of each file, output to the provided
# directory. Uses OpenAI Whisper.
# Note: latest PyPI openai-whisper package is broken with python >3.12. If you are building this locally, set up a local
# venv package with the git version (see https://github.com/openai/whisper/discussions/2410)

import whisper

model = whisper.load_model("small")
result = model.transcribe("sample.wav")
print(result["text"])