# Email Exporter Tests

This directory contains comprehensive tests for the Email Exporter application, organized with clear distinctions between unit and integration tests.

## Test Structure

The tests are organized using clear naming conventions to distinguish between unit and integration tests:

### Unit Tests (Fast, Isolated)

- **`test_unit_content_processor.py`** - Unit tests for the `ContentProcessor` class
  - HTML to text conversion (with mocked dependencies)
  - Quoted reply stripping
  - Whitespace normalization
  - Content validation
  - System-generated message detection
  - Email body extraction from multipart messages

- **`test_unit_email_processor.py`** - Unit tests for the `EmailProcessor` class
  - Individual method testing with mocks
  - Message processing workflow
  - Statistics tracking
  - Error handling
  - Batch processing logic

- **`test_unit_cache_manager.py`** - Unit tests for the `CacheManager` class
  - Cache operations and UID tracking
  - File I/O operations
  - Duplicate detection
  - Error handling and recovery

### Integration Tests (Slower, End-to-End)

- **`test_integration_content_email.py`** - Integration tests for ContentProcessor and EmailProcessor interaction
  - Complete processing workflows
  - Multi-message batch processing
  - Real-world email scenarios

- **`test_integration_cache.py`** - Integration tests for cache functionality with email processing
  - Cache integration with EmailProcessor
  - Duplicate detection during processing
  - End-to-end caching workflow

- **`test_integration_email_processor.py`** - Full email processing workflow integration tests
  - Complete email processing pipelines
  - HTML and multipart email handling
  - Real-world scenarios with minimal mocking

The tests are designed to run with pytest for better test discovery, reporting, and coverage analysis.

### Test Coverage

The tests cover all the functionality implemented in Task 4:

✅ **Email body extraction from multipart messages**
- Prioritizes plain text over HTML
- Handles various character encodings
- Skips attachments
- Processes both single-part and multipart messages

✅ **HTML to plain text conversion using html2text library**
- Uses BeautifulSoup for robust HTML parsing
- Removes script and style elements
- Configures html2text for optimal output
- Includes fallback mechanisms

✅ **BeautifulSoup integration for robust HTML parsing**
- Cleans HTML before conversion
- Handles malformed HTML gracefully
- Provides fallbacks when libraries unavailable

✅ **Content filtering and validation**
- Minimum word count validation (20+ words)
- System-generated message detection and exclusion
- Quoted reply and forwarded text removal
- Content quality assessment
- Whitespace normalization and cleaning

✅ **Whitespace normalization and line break standardization**
- Standardizes different line break formats
- Removes excessive whitespace
- Preserves paragraph structure
- Trims leading/trailing whitespace

## Running Tests

### Prerequisites

Make sure you have the required dependencies installed:

```bash
# Activate virtual environment
source .venv/bin/activate

# Install dependencies (if not already installed)
pip install beautifulsoup4 html2text python-dotenv pytest pytest-cov
```

### Running All Tests

```bash
# From the project root directory
pytest

# With coverage report
pytest --cov=src --cov-report=term-missing

# With verbose output
pytest -v
```

### Running Specific Test Types

```bash
# Run only unit tests (fast, isolated)
pytest tests/test_unit_* -v

# Run only integration tests (slower, end-to-end)
pytest tests/test_integration_* -v

# Run specific test files
pytest tests/test_unit_content_processor.py
pytest tests/test_unit_email_processor.py
pytest tests/test_unit_cache_manager.py
pytest tests/test_integration_content_email.py
pytest tests/test_integration_cache.py
pytest tests/test_integration_email_processor.py

# Run tests by pattern (e.g., all tests containing "content")
pytest -k "content"

# Run tests by markers (if you add pytest markers)
pytest -m "unit"
pytest -m "integration"
```

### Running Individual Test Files

```bash
# Run a specific test file
pytest tests/test_unit_content_processor.py

# Run a specific test class
pytest tests/test_unit_content_processor.py::TestContentProcessor

# Run a specific test method
pytest tests/test_unit_content_processor.py::TestContentProcessor::test_convert_html_to_text_with_libraries

# Run with detailed output for debugging
pytest tests/test_unit_content_processor.py -v -s

# Run a specific test and stop on first failure
pytest tests/test_unit_content_processor.py -x
```

### Running Tests with Advanced Options

```bash
# Run tests with coverage and generate HTML report
pytest --cov=src --cov-report=html

# Run tests in parallel (requires pytest-xdist)
pytest -n auto

# Run only failed tests from last run
pytest --lf

# Run tests that match a specific pattern
pytest -k "test_html or test_content"

# Run tests with maximum verbosity and show local variables on failure
pytest -vvv --tb=long

# Run tests and stop after first failure
pytest -x

# Run tests and enter debugger on failure (requires pytest-pdb)
pytest --pdb
```

## Test Categories

### Unit Tests (`test_unit_*`)
- **Purpose**: Test individual methods and functions in isolation
- **Characteristics**: Fast execution, extensive mocking, focused scope
- **Benefits**: Quick feedback, precise error localization, reliable CI/CD
- **Examples**: 
  - Individual ContentProcessor methods with mocked dependencies
  - EmailProcessor logic with mocked IMAP connections
  - CacheManager operations with temporary file systems

### Integration Tests (`test_integration_*`)
- **Purpose**: Test complete workflows end-to-end
- **Characteristics**: Slower execution, minimal mocking, broader scope
- **Benefits**: Verify component interactions, catch integration issues
- **Examples**:
  - Full email processing pipeline with real ContentProcessor
  - Cache integration with actual file I/O
  - Multi-component workflows with realistic data

### Test Organization Benefits
- **Clear Separation**: Easy to run fast unit tests during development
- **Selective Execution**: Run integration tests before commits/deployments
- **Maintainability**: Clear understanding of test scope and purpose
- **CI/CD Optimization**: Different test stages for different pipeline phases

## Key Test Scenarios

1. **HTML Processing**
   - Valid HTML conversion to text
   - Malformed HTML handling
   - Script/style tag removal
   - Library availability fallbacks

2. **Content Filtering**
   - System-generated message detection (auto-replies, delivery notifications, vacation messages, calendar invitations, security alerts)
   - Content length validation (minimum 20 words)
   - Alphabetic content ratio checks
   - Empty/whitespace handling

3. **Email Structure Handling**
   - Multipart message processing
   - Character encoding variations
   - Attachment skipping
   - Header extraction

4. **Content Cleaning**
   - Quoted reply removal (basic quotes, Gmail-style, Apple Mail)
   - Forwarded message stripping (various email client formats)
   - Whitespace normalization
   - Line break standardization

5. **Pipeline Integration**
   - End-to-end processing with multiple message types
   - Statistics tracking and validation
   - Error handling across the processing pipeline
   - Real-world email scenarios

## Maintenance

When adding new functionality:

1. Add corresponding unit tests following pytest conventions
2. Update integration tests if needed
3. Use pytest fixtures for common test setup
4. Run `pytest` to ensure all tests pass
5. Consider adding pytest markers for test categorization
6. Update this README if test structure changes

## Pytest Configuration

The project uses pytest with configuration in `pyproject.toml`:

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
addopts = "-v --cov=src"
```

This configuration:
- Sets the test directory to `tests/`
- Discovers all files matching `test_*.py`
- Runs with verbose output and source coverage by default

The tests are designed to be comprehensive and maintainable, providing confidence in the content processing functionality. Using pytest provides better test discovery, reporting, and integration with modern Python development workflows.