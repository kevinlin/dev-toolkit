# Dev Toolkit

A collection of development utilities and testbeds for various Python experiments and tools.

## Email Exporter

The main utility in this toolkit is the Email Exporter - a Python script that extracts and processes sent emails from Gmail, iCloud, or Outlook accounts via IMAP. It processes only sent messages, extracts clean body content while excluding quoted replies and duplicates, and outputs content to timestamped plain text files suitable for AI training.

### Features

- **Multi-Provider Support**: Works with Gmail, iCloud, and Outlook accounts
- **Secure Authentication**: Uses app-specific passwords for enhanced security
- **Content Filtering**: Excludes quoted replies, forwards, and system-generated messages
- **Duplicate Detection**: Skips duplicate content using hash comparison
- **Batch Processing**: Handles large mailboxes with pagination (500 messages per batch)
- **Progress Tracking**: Console logging with progress updates every 100 emails
- **Caching System**: Prevents reprocessing of already-handled emails
- **Error Recovery**: Robust error handling with retry logic for network issues

### Quick Start

1. Copy the environment template and configure your credentials:
```bash
cp .env.example .env
# Edit .env with your email provider, address, and app-specific password
```

2. Run the email exporter:
```bash
python email_exporter.py
```

See `.env.example` for detailed instructions on obtaining app-specific passwords for each provider.

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