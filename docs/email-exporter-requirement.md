# Email Exporter Script Specification (Gmail, iCloud & Outlook)

## Overview
This document defines the specification for a Python script that extracts and cleans the content of sent emails from Gmail, iCloud, or Outlook accounts, and aggregates them into plain text files for later use in AI training.

The script will:
- Connect to Gmail, iCloud, or Outlook via IMAP using app-specific passwords.
- Process only messages in the Sent folder.
- Extract and clean the user-authored body content.
- Exclude quoted replies, forwards, duplicates, and trivial messages.
- Save final outputs in timestamped `.txt` files per account.

---

## Features & Functional Requirements

### Authentication
- IMAP using app-specific passwords.
- Email credentials and provider type stored in `.env` file.
- Required `.env` fields must be validated at startup.

### Email Processing
- One-time execution, no user prompts.
- Supports Gmail, iCloud, or Outlook per run.
- Folder:
  - Gmail: `[Gmail]/Sent Mail`
  - iCloud: `Sent Messages`
  - Outlook: `Sent Items`
- Full mailbox traversal using pagination (batches of 500).
- Sequential message processing.
- Filter messages:
  - Exclude messages < 20 words.
  - Exclude system-generated content (e.g., auto-replies, receipts).
  - Exclude quoted replies and forwarded text.
  - Skip exact duplicates.

### Output
- One `.txt` file per run, named: `gmail-yyyyMMdd-HHmmss.txt`, `icloud-yyyyMMdd-HHmmss.txt`, or `outlook-yyyyMMdd-HHmmss.txt`
- Output directory: `/output` (created if not exists).
- UTF-8 encoded plain text.
- Only cleaned body text included (no metadata).
- Whitespace normalized (trimmed, line breaks normalized).

### Logging & Summary
- Console output only.
- Basic progress logged every 100 emails.
- Print summary at the end:
  - Total fetched
  - Skipped (short)
  - Skipped (duplicate)
  - Retained
- Show first 3 retained message previews.
- Print connected email address.

### Error Handling
- Console display of errors only (no file log).
- Retry logic for IMAP connection (up to 3 times).
- Exit with error if required `.env` fields missing.

### Caching
- Cache UIDs of processed emails to avoid duplicates on reruns.
- Cache files stored in `/output`, named per account:
  - `gmail.cache.json`
  - `icloud.cache.json`
  - `outlook.cache.json`
- No reset logic; manual deletion assumed.

### Code Architecture
- Single file: `main.py`
- Modular code structure within `main.py` for:
  - IMAP connection
  - HTML parsing & reply stripping
  - Deduplication
  - File output & logging
  - Caching

---

## Environment Configuration (`.env`)

### Gmail and iCloud (IMAP with App Passwords)
```dotenv
PROVIDER=gmail             # or icloud
EMAIL_ADDRESS=you@example.com
APP_PASSWORD=yourapppassword123
```

### Outlook (OAuth2 Authentication)
```dotenv
PROVIDER=outlook
EMAIL_ADDRESS=you@outlook.com
# APP_PASSWORD is ignored for Outlook (OAuth2 is used automatically)
```

**Note for Outlook users:** Microsoft has deprecated Basic Authentication (app passwords) for Outlook.com accounts as of September 2024. The email exporter automatically uses OAuth2 authentication for Outlook accounts, which provides better security and doesn't require app passwords.

---

## Testing Plan

### Unit Tests (manual or basic)
- Validate `.env` parsing and required fields
- Simulate IMAP connection (mock credentials)
- Test email body extraction:
  - HTML to plain text
  - Quoted/forwarded reply stripping
  - Word count threshold logic
- Cache read/write consistency
- Deduplication check (by body content)

### Dry Run Testing
- Use test email accounts with sample Sent messages
- Validate all summary stats match expectations
- Confirm output text file quality

### Edge Cases
- Large HTML emails with nested replies
- Duplicate content across different emails
- Multilingual content (verify it is retained)
- Timeouts during large batch fetches

---

## Implementation Notes
- Libraries:
  - `imaplib`, `email`, `bs4`, `dotenv`, `html2text`, `re`, `os`, `json`, `datetime`
- Platform: macOS
- Python 3.10+

---

## Deliverables
- `main.py` script
- `.env.example` file
- README with setup instructions and usage guide

---

End of specification.

