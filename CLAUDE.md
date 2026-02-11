# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A Python development toolkit containing:
- **Email Exporter** (`email_exporter.py`, `content_processor.py`, `outlook_oauth.py`): Extracts sent emails from Gmail/iCloud/Outlook with content filtering, duplicate detection, and batch processing
- **Maestro-to-Gherkin Transpiler** (`src/maestro-to-gherkin/`): Converts Maestro YAML mobile test flows to Cucumber Gherkin `.feature` files using Jinja2 templates
- **Image Renamer** (`rename_stock_images.py`): AI-powered batch image renaming using OpenAI vision API

## Build & Development Commands

```bash
# Install with dev dependencies
pip install -e .[dev]

# Lint
ruff check .
ruff check . --fix

# Format
ruff format .
ruff format --check .

# Run all tests (default includes coverage)
pytest

# Run unit tests only
pytest tests/test_unit_*

# Run integration tests only
pytest tests/test_integration_*

# Run a single test class/method
pytest tests/test_unit_email_processor.py::TestEmailProcessor::test_init_creates_content_processor

# Run tests matching a keyword
pytest -k "content"

# Security scan
bandit -r . --severity-level medium

# Dependency vulnerability scan
pip-audit --desc
```

## Architecture

### Email Exporter Pipeline

The email exporter uses a manager-based architecture with dependency injection:

- **`EmailExporterConfig`** — loads provider settings from `.env` (gmail/icloud/outlook)
- **`IMAPConnectionManager`** — handles IMAP connections with retry logic (Gmail/iCloud path)
- **`OutlookOAuth2Processor`** / **`OutlookOAuth2Client`** — Microsoft Graph API OAuth2 flow (Outlook path)
- **`ContentProcessor`** — extracts email body, converts HTML→text (BeautifulSoup + html2text), strips quoted replies, detects system-generated messages, validates content (min 20 words), computes SHA256 content hashes
- **`CacheManager`** — tracks processed UIDs in `{provider}.cache.json` for duplicate prevention
- **`OutputWriter`** — writes timestamped output files (`{provider}-yyyyMMdd-HHmmss.txt`)
- **`EmailProcessor`** — orchestrates the full pipeline, receives managers via constructor injection
- **`ProcessingStats`** — tracks counts, errors, and timing across the run

Optional dependencies use try/except imports with feature flags (`HTML_PROCESSING_AVAILABLE`, `OUTLOOK_OAUTH_AVAILABLE`) for graceful degradation.

### Maestro-to-Gherkin Transpiler

Loads multi-document YAML (appId + flow steps) → renders through Jinja2 template (`gherkin_template.j2`) → outputs `.feature` files.

## Testing Conventions

- **Unit tests**: `tests/test_unit_*.py` — isolated with `unittest.TestCase`, heavy use of `unittest.mock`
- **Integration tests**: `tests/test_integration_*.py` — end-to-end flows with minimal mocking
- Tests use `tempfile.mkdtemp()` for file I/O isolation with `setUp()`/`tearDown()` cleanup

## Tool Configuration

- **Ruff**: line-length=100, target=py38, rules: E/W/F/B/I/UP/C4/SIM/TCH (configured in `pyproject.toml`)
- **Pytest**: default args include `-v --cov=src --cov-report=term-missing --cov-report=xml`
- **Bandit**: excludes tests/.venv/venv, skips B101 (assert_used)

## CI Pipeline

GitHub Actions (`.github/workflows/ci.yml`) runs on push/PR to main/develop:
1. Ruff lint + format check
2. Bandit security scan
3. pip-audit dependency scan
4. Pytest with coverage → Codecov upload
5. Quality gate job that fails if any step above fails
