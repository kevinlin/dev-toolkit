# Implementation Plan

- [x] 1. Set up project structure and core configuration management
  - Create main.py file with basic imports and structure
  - Implement environment variable validation for PROVIDER, EMAIL_ADDRESS, and APP_PASSWORD
  - Create provider-specific configuration mapping for Gmail and iCloud IMAP settings
  - Add error handling for missing or invalid environment variables
  - _Requirements: 1.1, 1.2, 8.4_

- [x] 2. Implement IMAP connection management with retry logic
  - Create IMAP connection function with SSL support for Gmail and iCloud
  - Implement retry logic with exponential backoff (up to 3 attempts)
  - Add proper connection cleanup and error handling
  - Implement folder selection for provider-specific sent mail folders
  - _Requirements: 1.3, 1.4, 2.1, 2.2, 7.1_

- [x] 3. Create email fetching and pagination system
  - Implement UID-based email fetching with batch processing (500 messages per batch)
  - Create pagination logic to traverse entire mailbox without memory overflow
  - Add progress logging every 100 processed emails
  - Implement sequential message processing with proper error handling
  - Write unit tests for email fetching and pagination system
  - _Requirements: 2.3, 2.4, 2.5, 5.1, 7.2_

- [x] 4. Build content extraction and HTML processing
  - Implement email body extraction from multipart messages
  - Create HTML to plain text conversion using html2text library
  - Add BeautifulSoup integration for robust HTML parsing
  - Implement whitespace normalization and line break standardization
  - Write unit tests for content extraction and HTML processing
  - _Requirements: 3.5, 3.6, 4.6_

- [x] 5. Implement content filtering and validation
  - Create word count validation to exclude messages with fewer than 20 words
  - Implement system-generated content detection (auto-replies, receipts)
  - Build quoted reply and forwarded text stripping using regex patterns
  - Add content validation functions for meaningful email detection
  - **ENHANCED**: Add opening greetings filtering (Hi Krishna, Hello Ben, Dear Raina, etc.)
  - **ENHANCED**: Add Kevin Lin signature filtering (Best regards/Sincerely yours, Kevin Lin)
  - **ENHANCED**: Remove all blank lines from processed content
  - Write unit tests for content filtering and validation
  - _Requirements: 3.1, 3.2, 3.3_

- [x] 6. Create caching system for duplicate prevention
  - Implement JSON-based cache file management for processed UIDs
  - Create cache loading and saving functions for gmail.cache.json and icloud.cache.json
  - Add duplicate detection logic based on UID caching
  - Implement cache corruption recovery with new file creation
  - Write unit tests for cache operations and duplicate detection
  - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7, 7.5_

- [x] 7. Implement deduplication based on content comparison
  - Create content hashing system for exact duplicate detection
  - Implement body content comparison logic
  - Add duplicate tracking and skipping functionality
  - Integrate deduplication with caching system
  - Write unit tests for content hashing and deduplication logic
  - _Requirements: 3.4, 6.6_

- [x] 8. Build output file management system
  - Create output directory creation logic (/output folder)
  - Implement timestamped filename generation (provider-yyyyMMdd-HHmmss.txt format)
  - Add UTF-8 encoded file writing with proper content formatting
  - Create email delimiter system for separating individual messages in output
  - Write unit tests for file operations and output formatting
  - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7_

- [x] 9. Create comprehensive logging, error handling and summary reporting
  - Implement console progress logging with batch processing updates
  - Implement individual message processing error handling with continuation
  - Add timeout handling for batch fetch operations with retry logic
  - Create final summary statistics (total, skipped short, skipped duplicate, retained)
  - Add first 3 retained message preview functionality
  - Implement connected email address display
  - Add error logging to console with clear error messages
  - Write unit tests for logging, error handling scenarios and summary generation
  - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 7.1, 7.2, 7.3, 7.4, 8.5_

- [x] 10. Create modular class/function structure and code organization
  - The main entry point file has been renamed to: email_exporter.py (using underscore for Python import compatibility)
  - Code is already well-structured with modular classes following single responsibility principle:
    - EmailExporterConfig: Configuration validation and provider-specific settings
    - IMAPConnectionManager: IMAP connection handling with retry logic and error handling
    - ContentProcessor: Email content extraction, HTML parsing, content filtering and cleaning
    - CacheManager: UID caching and content hash tracking for duplicate prevention
    - OutputWriter: File creation and content writing for processed emails
    - EmailProcessor: Email fetching, processing orchestration and statistics tracking
    - ProcessingStats: Enhanced statistics tracking with error categorization and timing
  - All functions have clear naming and comprehensive documentation with docstrings
  - Updated all unit tests to import from the renamed module (email_exporter)
  - All existing tests continue to pass after refactoring
  - _Requirements: 8.1, 8.2, 8.3, 8.5_

- [x] 11. Add Outlook/Hotmail mail support with OAuth2 authentication
  - ✅ Add Outlook provider configuration to EmailExporterConfig.PROVIDER_CONFIGS
  - ✅ Implement OAuth2 authentication using Microsoft Graph API (IMAP deprecated by Microsoft)
  - ✅ Create OutlookOAuth2Client class with MSAL integration for secure authentication
  - ✅ Support multiple authentication flows: device code flow and authorization code flow
  - ✅ Implement Microsoft Graph API integration for accessing sent messages
  - ✅ Create OutlookOAuth2Processor class for Graph API email processing
  - ✅ Add automatic HTML to text conversion using html2text library
  - ✅ Support all Outlook domain formats (@outlook.com, @hotmail.com, @live.com, @msn.com)
  - ✅ Add Outlook cache file support (outlook.cache.json) with message ID tracking
  - ✅ Update environment validation to make APP_PASSWORD optional for Outlook
  - ✅ Implement automatic browser-based OAuth2 authentication with token caching
  - ✅ Add comprehensive error handling for OAuth2 and Graph API operations
  - ✅ Test OAuth2 integration with proper dependency management
  - ✅ Update output file naming to support "outlook-yyyyMMdd-HHmmss.txt" format
  - ✅ Create unified main() function supporting both IMAP (Gmail/iCloud) and OAuth2 (Outlook)
  - ✅ Update documentation to reflect OAuth2 requirement for Outlook accounts
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 2.1, 2.2, 4.1, 4.2, 6.1, 6.2, 6.3, 8.4_