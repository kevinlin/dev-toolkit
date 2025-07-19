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

- [ ] 3. Create email fetching and pagination system
  - Implement UID-based email fetching with batch processing (500 messages per batch)
  - Create pagination logic to traverse entire mailbox without memory overflow
  - Add progress logging every 100 processed emails
  - Implement sequential message processing with proper error handling
  - _Requirements: 2.3, 2.4, 2.5, 5.1, 7.2_

- [ ] 4. Build content extraction and HTML processing
  - Implement email body extraction from multipart messages
  - Create HTML to plain text conversion using html2text library
  - Add BeautifulSoup integration for robust HTML parsing
  - Implement whitespace normalization and line break standardization
  - _Requirements: 3.5, 3.6, 4.6_

- [ ] 5. Implement content filtering and validation
  - Create word count validation to exclude messages with fewer than 20 words
  - Implement system-generated content detection (auto-replies, receipts)
  - Build quoted reply and forwarded text stripping using regex patterns
  - Add content validation functions for meaningful email detection
  - _Requirements: 3.1, 3.2, 3.3_

- [ ] 6. Create caching system for duplicate prevention
  - Implement JSON-based cache file management for processed UIDs
  - Create cache loading and saving functions for gmail.cache.json and icloud.cache.json
  - Add duplicate detection logic based on UID caching
  - Implement cache corruption recovery with new file creation
  - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7, 7.5_

- [ ] 7. Build output file management system
  - Create output directory creation logic (/output folder)
  - Implement timestamped filename generation (provider-yyyyMMdd-HHmmss.txt format)
  - Add UTF-8 encoded file writing with proper content formatting
  - Create email delimiter system for separating individual messages in output
  - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7_

- [ ] 8. Implement deduplication based on content comparison
  - Create content hashing system for exact duplicate detection
  - Implement body content comparison logic
  - Add duplicate tracking and skipping functionality
  - Integrate deduplication with caching system
  - _Requirements: 3.4, 6.6_

- [ ] 9. Create comprehensive logging and summary reporting
  - Implement console progress logging with batch processing updates
  - Create final summary statistics (total, skipped short, skipped duplicate, retained)
  - Add first 3 retained message preview functionality
  - Implement connected email address display
  - Add error logging to console with clear error messages
  - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5_

- [ ] 10. Add comprehensive error handling and recovery
  - Implement individual message processing error handling with continuation
  - Add timeout handling for batch fetch operations with retry logic
  - Create file write operation error handling with graceful exit
  - Add IMAP connection error recovery and clear error messaging
  - _Requirements: 7.1, 7.2, 7.3, 7.4, 8.5_

- [ ] 11. Create modular function structure and code organization
  - Refactor code into modular functions following single responsibility principle
  - Organize functions for IMAP connection, HTML parsing, deduplication, file output, logging, and caching
  - Implement clear function naming and documentation
  - Add proper exception handling for each operation type
  - _Requirements: 8.1, 8.2, 8.3, 8.5_

- [ ] 12. Create configuration files and documentation
  - Create .env.example file with required environment variable template
  - Write README.md with setup instructions and usage guide
  - Add requirements.txt file with necessary Python dependencies
  - Create usage examples and troubleshooting guide
  - _Requirements: 1.1, 8.4_

- [ ] 13. Implement end-to-end integration and testing
  - Create main execution flow that integrates all components
  - Add startup validation and initialization sequence
  - Implement graceful shutdown and cleanup procedures
  - Test complete workflow with sample email data
  - Validate output file format and content quality
  - _Requirements: 1.1, 1.5, 2.4, 4.6, 5.2, 5.3_