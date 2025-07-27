# Dev Toolkit

A collection of development utilities and testbeds for various Python experiments and tools.

## Email Exporter

The main utility in this toolkit is the Email Exporter - a Python script that extracts and processes sent emails from Gmail, iCloud, or Outlook accounts. It processes only sent messages, extracts clean body content while excluding quoted replies and duplicates, and outputs content to timestamped plain text files suitable for AI training.

### Features

- **Multi-Provider Support**: Works with Gmail, iCloud, and Outlook accounts
- **Modern Authentication**: 
  - Gmail & iCloud: IMAP with app-specific passwords
  - Outlook: OAuth2 with Microsoft Graph API (browser-based, more secure)
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
# Edit .env with your email provider and address
# For Gmail/iCloud: Add your app-specific password  
# For Outlook: OAuth2 authentication is handled automatically
```

2. Run the email exporter:
```bash
python email_exporter.py
```

**For Outlook accounts**: A browser window will open automatically for OAuth2 authentication. No app password needed.

**For Gmail/iCloud accounts**: See `.env.example` for detailed instructions on obtaining app-specific passwords.

## Setup

### Development Installation

1. Create and activate a virtual environment:
```bash
python -m venv .venv
source .venv/bin/activate  # On Unix/macOS
# or
.venv\Scripts\activate  # On Windows
```

2. Install the project with development dependencies:
```bash
pip install -e .[dev]
```

### Alternative Setup with uv

This project also supports `uv` for dependency management:

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
uv pip install -e .[dev]
```

## Development Tools

This project includes a comprehensive development setup with linting, testing, and security scanning.

### Install Development Dependencies
```bash
pip install -e .[dev]
```

### Linting and Code Quality

**Run linting checks:**
```bash
ruff check .
```

**Check code formatting:**
```bash
ruff format --check .
```

**Auto-format code:**
```bash
ruff format .
```

**Auto-fix linting issues:**
```bash
ruff check . --fix
```

**Combined format and fix:**
```bash
ruff format . && ruff check . --fix
```

### Testing

**Run tests:**
```bash
pytest
```

**Run tests with coverage:**
```bash
pytest --cov=src --cov-report=term-missing
```

**Run tests with HTML coverage report:**
```bash
pytest --cov=src --cov-report=term-missing --cov-report=html
```

**Run tests with XML coverage (for CI):**
```bash
pytest --cov=src --cov-report=xml
```

### Security Scanning

**Run Bandit security scan:**
```bash
bandit -r . --severity-level medium
```

**Run dependency vulnerability scan:**
```bash
pip-audit --desc
```

**Generate security reports:**
```bash
bandit -r . -f json -o bandit-report.json
pip-audit --desc --output=json --output-file=pip-audit-report.json
```

### Combined Workflows

**Full quality check (recommended before commits):**
```bash
# Run all checks in sequence
ruff check . && \
ruff format --check . && \
bandit -r . --severity-level medium && \
pip-audit --desc && \
pytest --cov=src --cov-report=term-missing
```

**Format and fix all issues:**
```bash
# Format code and fix auto-fixable issues
ruff format . && ruff check . --fix
```

### Clean Up Generated Files
```bash
# Remove test and coverage artifacts
rm -rf .pytest_cache/ htmlcov/ .coverage coverage.xml

# Remove security scan reports
rm -rf bandit-report.json pip-audit-report.json

# Remove Python cache files
find . -type f -name "*.pyc" -delete
find . -type d -name "__pycache__" -delete
```

### Continuous Integration

GitHub Actions automatically runs all checks on every push and pull request:
- **Linting**: Ruff for code quality and formatting
- **Testing**: pytest with coverage reporting
- **Security**: Bandit for security issues + pip-audit for dependency vulnerabilities
- **Multi-Python**: Tests against Python 3.8, 3.9, 3.10, and 3.11

## Project Structure

```
dev-toolkit/
├── .github/workflows/  # GitHub Actions CI/CD
├── src/               # Source code
├── tests/             # Test files
├── examples/          # Example usage and testbeds
├── docs/              # Documentation
└── pyproject.toml     # Project configuration and dependencies
```

## Development Workflow

1. **Before starting work:**
   ```bash
   # Activate virtual environment
   source .venv/bin/activate
   
   # Install/update dependencies
   pip install -e .[dev]
   ```

2. **During development:**
   ```bash
   # Format your code
   ruff format .
   
   # Check for issues
   ruff check . --fix
   
   # Run tests
   pytest
   ```

3. **Before committing:**
   ```bash
   # Run full quality check
   ruff check . && \
   ruff format --check . && \
   bandit -r . --severity-level medium && \
   pip-audit --desc && \
   pytest --cov=src --cov-report=term-missing
   ```

## Development

- Use `ruff` for linting and formatting (configured in `pyproject.toml`)
- Use `pytest` for running tests with coverage
- Use `bandit` for security scanning
- Follow PEP 8 style guidelines
- All development dependencies are managed in `pyproject.toml`

## License

MIT 