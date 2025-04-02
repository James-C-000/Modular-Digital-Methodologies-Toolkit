from PyInstaller.utils.hooks import collect_all

# Collect all pydantic submodules
datas, binaries, hiddenimports = collect_all('pydantic')

# Explicitly add the problematic submodules
hiddenimports.extend([
    'pydantic.deprecated.decorator',
    'pydantic.deprecated.class_validators',
    'pydantic.deprecated.config',
    'pydantic.deprecated.tools',
    'pydantic.alias_generators',
    'pydantic.networks',
    'pydantic.color',
    'pydantic.dataclasses',
    'pydantic.datetime_parse',
])