# Requirements Document

## Introduction

The Email Exporter Script is a Python application that extracts and processes sent emails from Gmail or iCloud accounts via IMAP. The script connects using app-specific passwords, processes only sent messages, extracts clean body content while excluding quoted replies and duplicates, and outputs the content to timestamped plain text files suitable for AI training purposes.

## Requirements

### Requirement 1

**User Story:** As a data scientist, I want to authenticate to Gmail or iCloud using app-specific passwords, so that I can securely access my sent emails without compromising my main account credentials.

#### Acceptance Criteria

1. WHEN the script starts THEN the system SHALL validate that all required environment variables (PROVIDER, EMAIL_ADDRESS, APP_PASSWORD) are present in the .env file
2. IF any required environment variable is missing THEN the system SHALL exit with an error message indicating which fields are missing
3. WHEN connecting to the email provider THEN the system SHALL use IMAP protocol with the provided app-specific password
4. WHEN IMAP connection fails THEN the system SHALL retry up to 3 times before failing
5. WHEN authentication is successful THEN the system SHALL log the connected email address to console

### Requirement 2

**User Story:** As a user, I want the script to process only sent emails from the appropriate folder, so that I can extract content I authored rather than received messages.

#### Acceptance Criteria

1. WHEN the provider is Gmail THEN the system SHALL connect to the "[Gmail]/Sent Mail" folder
2. WHEN the provider is iCloud THEN the system SHALL connect to the "Sent Messages" folder
3. WHEN processing emails THEN the system SHALL traverse the entire mailbox using pagination with batches of 500 messages
4. WHEN processing messages THEN the system SHALL process them sequentially in chronological order
5. WHEN fetching message UIDs THEN the system SHALL handle large mailboxes without memory overflow

### Requirement 3

**User Story:** As a user, I want the script to filter out low-quality content, so that the output contains only meaningful email content suitable for training purposes.

#### Acceptance Criteria

1. WHEN processing an email THEN the system SHALL exclude messages with fewer than 20 words
2. WHEN processing an email THEN the system SHALL exclude system-generated content such as auto-replies and delivery receipts
3. WHEN processing an email THEN the system SHALL strip quoted replies and forwarded text from the body
4. WHEN processing an email THEN the system SHALL skip exact duplicates based on body content comparison
5. WHEN extracting body content THEN the system SHALL convert HTML to plain text while preserving meaningful formatting
6. WHEN extracting body content THEN the system SHALL normalize whitespace by trimming and standardizing line breaks

### Requirement 4

**User Story:** As a user, I want the processed emails to be saved in organized output files, so that I can easily access and use the extracted content.

#### Acceptance Criteria

1. WHEN the script completes processing THEN the system SHALL create one output file per run
2. WHEN creating the output file THEN the system SHALL name it using the format "gmail-yyyyMMdd-HHmmss.txt" or "icloud-yyyyMMdd-HHmmss.txt"
3. WHEN creating the output file THEN the system SHALL save it in the "/output" directory
4. IF the output directory does not exist THEN the system SHALL create it automatically
5. WHEN writing to the output file THEN the system SHALL use UTF-8 encoding
6. WHEN writing to the output file THEN the system SHALL include only cleaned body text without metadata
7. WHEN writing to the output file THEN the system SHALL separate individual emails with clear delimiters

### Requirement 5

**User Story:** As a user, I want to see progress and summary information during execution, so that I can monitor the script's performance and understand the results.

#### Acceptance Criteria

1. WHEN processing emails THEN the system SHALL log progress to console every 100 processed emails
2. WHEN the script completes THEN the system SHALL display a summary including total fetched, skipped (short), skipped (duplicate), and retained message counts
3. WHEN the script completes THEN the system SHALL show previews of the first 3 retained messages
4. WHEN errors occur THEN the system SHALL display error messages to console only
5. WHEN the script starts THEN the system SHALL display the connected email address

### Requirement 6

**User Story:** As a user, I want the script to cache processed emails, so that I can avoid reprocessing the same content on subsequent runs.

#### Acceptance Criteria

1. WHEN processing emails THEN the system SHALL cache UIDs of processed emails to avoid duplicates on reruns
2. WHEN creating cache files THEN the system SHALL store them in the "/output" directory
3. WHEN the provider is Gmail THEN the system SHALL name the cache file "gmail.cache.json"
4. WHEN the provider is iCloud THEN the system SHALL name the cache file "icloud.cache.json"
5. WHEN starting a new run THEN the system SHALL load existing cache data if available
6. WHEN processing a message THEN the system SHALL check if the UID exists in cache before processing
7. WHEN completing processing THEN the system SHALL update the cache file with new UIDs

### Requirement 7

**User Story:** As a user, I want the script to handle errors gracefully, so that temporary issues don't cause complete failure and I understand what went wrong.

#### Acceptance Criteria

1. WHEN IMAP connection fails THEN the system SHALL retry up to 3 times with exponential backoff
2. WHEN individual message processing fails THEN the system SHALL log the error and continue with the next message
3. WHEN timeout occurs during batch fetch THEN the system SHALL retry the current batch once before moving to the next
4. WHEN file write operations fail THEN the system SHALL display a clear error message and exit gracefully
5. WHEN cache file is corrupted THEN the system SHALL create a new cache file and continue processing

### Requirement 8

**User Story:** As a developer, I want the code to be well-structured and maintainable, so that I can easily modify or extend the functionality.

#### Acceptance Criteria

1. WHEN implementing the solution THEN the system SHALL be contained in a single "main.py" file
2. WHEN structuring the code THEN the system SHALL use modular functions for IMAP connection, HTML parsing, deduplication, file output, logging, and caching
3. WHEN implementing functions THEN the system SHALL follow single responsibility principle with clear function names
4. WHEN handling configuration THEN the system SHALL validate environment variables at startup
5. WHEN implementing error handling THEN the system SHALL use appropriate exception handling for each operation type