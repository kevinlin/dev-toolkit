# Dev Toolkit

A collection of development utilities and testbeds for various Python experiments and tools.

## Setup

This project uses `uv` for dependency management. To get started:

1. Install uv (if not already installed):
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

2. Create and activate the virtual environment:
```bash
uv venv
source .venv/bin/activate  # On Unix/macOS
# or
.venv\Scripts\activate  # On Windows
```

3. Install dependencies:
```bash
uv pip install -e .
```

4. If you have a `.env` file in the project root, export the environment variables:
```bash
set -a; . ./.env; set +a
```

## Project Structure

```
dev-toolkit/
├── src/           # Source code
├── tests/         # Test files
├── examples/      # Example usage and testbeds
└── docs/          # Documentation
```

## Development

- Use `pytest` for running tests
- Use `ruff` for linting and formatting
- Follow PEP 8 style guidelines

## License

MIT 