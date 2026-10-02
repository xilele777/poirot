# Poirot

An experimental deep-research agent kernel for developers, with a ReAct loop, context management, persistent memory, skills, and CLI/TUI interfaces.

This independently maintained project is undergoing reliability work. Automatic skill evolution/rollback is not connected to application scheduling. Specialist evolution/evaluation lacks application-level dependencies and is rejected when enabled. Ordinary delegation and manual skill evolution remain available with appropriate configuration.

## Quick start

Requires Python 3.12+:

```sh
git clone https://github.com/xilele777/poirot.git
cd poirot
python -m venv .venv
# Windows: .venv/Scripts/Activate.ps1
# Linux/macOS: source .venv/bin/activate
pip install -e ".[dev]"
# Copy .env.example to .env and configure a provider API key.
poirot
```

Sandbox tools require explicit configuration. Local mode executes host processes; Docker mode requires the docker extra and a running daemon. Memory uses BM25 with whitespace tokenization. Session checkpoints remain in-process. Passing deterministic tests does not establish real-model research quality or Docker integration readiness.

## Documentation and validation

- [Current README](../README.md)
- [Capabilities and limitations](../docs/capabilities-and-limitations.md)
- [Development and verification](../docs/development.md)
- [English command reference](../USAGE.md)
- [Chinese guide](USAGE.zh-CN.md) / [Japanese guide](USAGE.ja.md)

```sh
python -m pytest -q
python scripts/check_wheel.py
```

## Provenance and license

Derived from [HezaoHezao/poirot](https://github.com/HezaoHezao/poirot), preserving original history and attribution. [MIT](../LICENSE); see [third-party notices](../THIRD_PARTY_LICENSES.md).
