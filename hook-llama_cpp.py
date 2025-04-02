from PyInstaller.utils.hooks import collect_dynamic_libs

# Collect all dynamic libraries for llama_cpp
binaries = collect_dynamic_libs('llama_cpp')