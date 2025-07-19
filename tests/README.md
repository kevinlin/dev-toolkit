# Email Exporter Unit Tests

This directory contains comprehensive unit tests for the Email Exporter application, specifically focusing on the content extraction and HTML processing functionality implemented in Task 4.

## Test Structure

### Test Files

- **`test_content_processor.py`** - Tests for the `ContentProcessor` class
  - HTML to text conversion
  - Quoted reply stripping
  - Whitespace normalization
  - Content validation
  - System-generated message detection
  - Email body extraction from multipart messages

- **`test_email_processor.py`** - Tests for the `EmailProcessor` class changes
  - Integration with `ContentProcessor`
  - Message processing workflow
  - Statistics tracking
  - Error handling

- **`test_integration.py`** - End-to-end integration tests
  - Complete processing workflows
  - Multi-message batch processing
  - Real-world scenarios

- **`test_content_filtering.py`** - Standalone content filtering validation tests
  - Word count validation (minimum 20 words)
  - System-generated content detection (auto-replies, delivery notifications, etc.)
  - Quoted reply and forwarded text stripping
  - HTML to text conversion validation
  - Whitespace normalization testing
  - Content quality validation

- **`test_integration_filtering.py`** - Integration tests for content filtering pipeline
  - End-to-end email processing with filtering
  - Multi-message processing with various content types
  - Statistics validation for filtering results
  - Real-world email scenarios including HTML, quoted replies, and system messages

- **`run_tests.py`** - Test runner script

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
uv pip install beautifulsoup4 html2text python-dotenv
```

### Running All Tests

```bash
# From the project root directory
.venv/bin/python tests/run_tests.py
```

### Running Specific Test Suites

```bash
# Content processor tests only
.venv/bin/python tests/run_tests.py content

# Email processor tests only
.venv/bin/python tests/run_tests.py processor

# Integration tests only
.venv/bin/python tests/run_tests.py integration

# Processing stats tests only
.venv/bin/python tests/run_tests.py stats
```

### Running Individual Test Files

```bash
# Run a specific test file
.venv/bin/python -m unittest tests.test_content_processor

# Run the new content filtering test file directly
cd tests && python test_content_filtering.py

# Run the new integration filtering test file directly
cd tests && python test_integration_filtering.py

# Run a specific test class
.venv/bin/python -m unittest tests.test_content_processor.TestContentProcessor

# Run a specific test method
.venv/bin/python -m unittest tests.test_content_processor.TestContentProcessor.test_convert_html_to_text_with_libraries
```

### Running Standalone Test Files

The following test files can be run independently and include their own test runners:

```bash
# Content filtering validation tests (standalone)
cd tests && python test_content_filtering.py

# Integration filtering tests (standalone)
cd tests && python test_integration_filtering.py
```

## Test Results

All tests should pass:

```
----------------------------------------------------------------------
Ran 56 tests in 0.028s

OK
```

The test suite includes:
- **33 tests** for ContentProcessor functionality
- **12 tests** for EmailProcessor changes  
- **3 tests** for ProcessingStats
- **8 tests** for end-to-end integration scenarios
- **6 additional standalone test categories** for content filtering validation
- **1 comprehensive integration test** for email processing pipeline with filtering

## Test Categories

### Unit Tests
- Test individual methods and functions in isolation
- Use mocking to isolate dependencies
- Focus on edge cases and error handling

### Integration Tests
- Test complete workflows end-to-end
- Verify interaction between components
- Test real-world scenarios with actual email message structures

### Standalone Validation Tests
- Self-contained test files that can run independently
- Focus on specific functionality areas (content filtering, validation)
- Include comprehensive test scenarios and detailed output

### Error Handling Tests
- Verify graceful handling of exceptions
- Test fallback mechanisms
- Ensure system stability under error conditions

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

1. Add corresponding unit tests
2. Update integration tests if needed
3. Consider if standalone validation tests are appropriate
4. Ensure all tests pass
5. Update this README if test structure changes

The tests are designed to be comprehensive and maintainable, providing confidence in the content processing functionality. The addition of standalone test files (`test_content_filtering.py` and `test_integration_filtering.py`) provides focused validation of specific functionality areas with detailed test output and independent execution capabilities.