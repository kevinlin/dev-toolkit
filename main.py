#!/usr/bin/env python3
"""
Email Exporter Script

Extracts and processes sent emails from Gmail or iCloud accounts via IMAP.
Processes only sent messages, extracts clean body content while excluding 
quoted replies and duplicates, and outputs content to timestamped plain text files.
"""

import os
import sys
import imaplib
import time
import email
import email.message
import json
import datetime
import hashlib  # Add hashlib import for content hashing
from dataclasses import dataclass
from typing import Optional, Iterator, List, Set

# Try to import dotenv, but continue without it if not available
try:
    from dotenv import load_dotenv
    DOTENV_AVAILABLE = True
except ImportError:
    DOTENV_AVAILABLE = False
    def load_dotenv():
        pass

# Import HTML processing libraries
try:
    from bs4 import BeautifulSoup
    import html2text
    HTML_PROCESSING_AVAILABLE = True
except ImportError:
    HTML_PROCESSING_AVAILABLE = False
    print("Warning: HTML processing libraries not available. Install with: pip install beautifulsoup4 html2text")

import re


@dataclass
class ProviderConfig:
    """Configuration for email provider IMAP settings"""
    imap_server: str
    port: int
    sent_folder: str


@dataclass
class ProcessingStats:
    """Statistics for email processing with enhanced error tracking and timing"""
    total_fetched: int = 0
    skipped_short: int = 0
    skipped_duplicate: int = 0
    skipped_system: int = 0
    retained: int = 0
    errors: int = 0
    
    # Enhanced error categorization
    fetch_errors: int = 0
    timeout_errors: int = 0
    processing_errors: int = 0
    cache_errors: int = 0
    output_errors: int = 0
    
    # Timing information
    start_time: Optional[datetime.datetime] = None
    end_time: Optional[datetime.datetime] = None
    
    def start_processing(self) -> None:
        """Mark the start of processing"""
        self.start_time = datetime.datetime.now()
    
    def end_processing(self) -> None:
        """Mark the end of processing"""
        self.end_time = datetime.datetime.now()
    
    def get_processing_duration(self) -> Optional[str]:
        """Get formatted processing duration"""
        if self.start_time and self.end_time:
            duration = self.end_time - self.start_time
            total_seconds = int(duration.total_seconds())
            hours, remainder = divmod(total_seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            
            if hours > 0:
                return f"{hours}h {minutes}m {seconds}s"
            elif minutes > 0:
                return f"{minutes}m {seconds}s"
            else:
                return f"{seconds}s"
        return None
    
    def increment_error_type(self, error_type: str) -> None:
        """Increment specific error type and total errors"""
        self.errors += 1
        
        if error_type == 'fetch':
            self.fetch_errors += 1
        elif error_type == 'timeout':
            self.timeout_errors += 1
        elif error_type == 'processing':
            self.processing_errors += 1
        elif error_type == 'cache':
            self.cache_errors += 1
        elif error_type == 'output':
            self.output_errors += 1
    
    def get_summary(self) -> str:
        """Get a comprehensive formatted summary of processing statistics"""
        duration_str = self.get_processing_duration()
        duration_line = f"\n  Processing time: {duration_str}" if duration_str else ""
        
        summary = (f"Processing Summary:\n"
                  f"  Total fetched: {self.total_fetched}\n"
                  f"  Skipped (short): {self.skipped_short}\n"
                  f"  Skipped (duplicate): {self.skipped_duplicate}\n"
                  f"  Skipped (system): {self.skipped_system}\n"
                  f"  Retained: {self.retained}\n"
                  f"  Total errors: {self.errors}{duration_line}")
        
        # Add detailed error breakdown if there are errors
        if self.errors > 0:
            error_details = []
            if self.fetch_errors > 0:
                error_details.append(f"fetch: {self.fetch_errors}")
            if self.timeout_errors > 0:
                error_details.append(f"timeout: {self.timeout_errors}")
            if self.processing_errors > 0:
                error_details.append(f"processing: {self.processing_errors}")
            if self.cache_errors > 0:
                error_details.append(f"cache: {self.cache_errors}")
            if self.output_errors > 0:
                error_details.append(f"output: {self.output_errors}")
            
            if error_details:
                summary += f"\n  Error breakdown: {', '.join(error_details)}"
        
        # Add processing efficiency metrics
        if self.total_fetched > 0:
            retention_rate = (self.retained / self.total_fetched) * 100
            error_rate = (self.errors / self.total_fetched) * 100
            summary += f"\n  Retention rate: {retention_rate:.1f}%"
            summary += f"\n  Error rate: {error_rate:.1f}%"
        
        return summary
    
    def get_quick_stats(self) -> str:
        """Get a quick one-line summary for progress logging"""
        return f"processed: {self.total_fetched}, retained: {self.retained}, errors: {self.errors}"


class EmailExporterConfig:
    """Handles configuration validation and provider-specific settings"""
    
    # Provider-specific IMAP configurations
    PROVIDER_CONFIGS = {
        'gmail': ProviderConfig('imap.gmail.com', 993, '[Gmail]/Sent Mail'),
        'icloud': ProviderConfig('imap.mail.me.com', 993, '"Sent Messages"')
    }
    
    def __init__(self):
        self.provider: Optional[str] = None
        self.email_address: Optional[str] = None
        self.app_password: Optional[str] = None
        self.imap_server: Optional[str] = None
        self.sent_folder: Optional[str] = None
        self.port: int = 993
    
    def validate_environment(self) -> None:
        """
        Validate that all required environment variables are present.
        Exits with error message if any required fields are missing.
        """
        # Load environment variables from .env file if dotenv is available
        if DOTENV_AVAILABLE:
            load_dotenv()
        else:
            print("Warning: python-dotenv not installed. Reading environment variables directly.")
        
        # Required environment variables
        required_vars = ['PROVIDER', 'EMAIL_ADDRESS', 'APP_PASSWORD']
        missing_vars = []
        
        # Check for missing environment variables
        for var in required_vars:
            value = os.getenv(var)
            if not value or value.strip() == '':
                missing_vars.append(var)
        
        if missing_vars:
            print(f"Error: Missing required environment variables: {', '.join(missing_vars)}")
            print("Please ensure your .env file contains:")
            for var in missing_vars:
                print(f"  {var}=your_value_here")
            sys.exit(1)
        
        # Set configuration values
        self.provider = os.getenv('PROVIDER').strip().lower()
        self.email_address = os.getenv('EMAIL_ADDRESS').strip()
        self.app_password = os.getenv('APP_PASSWORD').strip()
        
        # Validate provider
        if self.provider not in self.PROVIDER_CONFIGS:
            print(f"Error: Invalid PROVIDER '{self.provider}'. Supported providers: {', '.join(self.PROVIDER_CONFIGS.keys())}")
            sys.exit(1)
        
        # Set provider-specific configuration
        provider_config = self.PROVIDER_CONFIGS[self.provider]
        self.imap_server = provider_config.imap_server
        self.sent_folder = provider_config.sent_folder
        self.port = provider_config.port
        
        print(f"Configuration validated successfully for {self.provider}")
    
    def get_imap_settings(self) -> tuple[str, int, str]:
        """
        Get IMAP server settings for the configured provider.
        
        Returns:
            tuple: (imap_server, port, sent_folder)
        """
        return (self.imap_server, self.port, self.sent_folder)


class IMAPConnectionManager:
    """Manages IMAP connections with retry logic and error handling"""
    
    def __init__(self, config: EmailExporterConfig):
        self.config = config
        self.connection: Optional[imaplib.IMAP4_SSL] = None
        self.max_retries = 3
        self.is_connected = False
        self.fetch_timeout = 60  # Add timeout for fetch operations (60 seconds)
    
    def connect(self) -> bool:
        """
        Establish IMAP connection with retry logic and exponential backoff.
        
        Returns:
            bool: True if connection successful, False otherwise
        """
        for attempt in range(self.max_retries):
            try:
                print(f"Attempting IMAP connection to {self.config.imap_server}:{self.config.port} (attempt {attempt + 1}/{self.max_retries})")
                
                # Create SSL IMAP connection with timeout
                self.connection = imaplib.IMAP4_SSL(self.config.imap_server, self.config.port)
                # Set socket timeout for all operations
                self.connection.sock.settimeout(self.fetch_timeout)
                
                # Authenticate with app password
                self.connection.login(self.config.email_address, self.config.app_password)
                
                self.is_connected = True
                print(f"Successfully connected to {self.config.provider} account: {self.config.email_address}")
                return True
                
            except imaplib.IMAP4.error as e:
                error_msg = f"IMAP authentication error: {str(e)}"
                if attempt == self.max_retries - 1:
                    print(f"Error: {error_msg}")
                    return False
                else:
                    print(f"Warning: {error_msg} - retrying...")
                    
            except Exception as e:
                error_msg = f"Connection error: {str(e)}"
                if attempt == self.max_retries - 1:
                    print(f"Error: {error_msg}")
                    return False
                else:
                    print(f"Warning: {error_msg} - retrying...")
            
            # Exponential backoff: wait 1s, 2s, 4s between attempts
            if attempt < self.max_retries - 1:
                wait_time = 2 ** attempt
                print(f"Waiting {wait_time} seconds before retry...")
                time.sleep(wait_time)
        
        return False
    
    def list_folders(self) -> list[str]:
        """
        List all available IMAP folders to help troubleshoot folder selection issues.
        
        Returns:
            list: List of folder names
        """
        if not self.is_connected or not self.connection:
            print("Error: Not connected to IMAP server")
            return []
        
        try:
            # List all folders
            status, folders = self.connection.list()
            
            if status != 'OK':
                print(f"Error: Failed to list folders: {folders}")
                return []
            
            folder_names = []
            print("Available IMAP folders:")
            for folder in folders:
                # Parse folder name from IMAP response
                # Format is typically: b'(\\HasNoChildren) "/" "INBOX"'
                folder_str = folder.decode('utf-8') if isinstance(folder, bytes) else str(folder)
                
                # Extract folder name (last quoted part)
                parts = folder_str.split('"')
                if len(parts) >= 3:
                    folder_name = parts[-2]  # Second to last quoted part is the folder name
                    folder_names.append(folder_name)
                    print(f"  - {folder_name}")
            
            return folder_names
            
        except Exception as e:
            print(f"Error listing folders: {str(e)}")
            return []
    
    def select_sent_folder(self) -> bool:
        """
        Select the provider-specific sent mail folder.
        
        Returns:
            bool: True if folder selection successful, False otherwise
        """
        if not self.is_connected or not self.connection:
            print("Error: Not connected to IMAP server")
            return False
        
        try:
            # Try different approaches to select the sent folder
            folder_variations = [
                self.config.sent_folder,  # Original: "Sent Messages"
                f'"{self.config.sent_folder}"',  # Quoted: "Sent Messages"
                f"'{self.config.sent_folder}'",  # Single quoted: 'Sent Messages'
                self.config.sent_folder.replace(' ', '_'),  # Underscore: "Sent_Messages"
                'INBOX.Sent Messages',  # INBOX prefix
                'INBOX/Sent Messages',  # INBOX with slash
            ]
            
            for folder_attempt in folder_variations:
                print(f"Trying to select folder: {folder_attempt}")
                try:
                    status, data = self.connection.select(folder_attempt)
                    if status == 'OK':
                        print(f"Successfully selected folder: {folder_attempt}")
                        # Update config for future use
                        self.config.sent_folder = folder_attempt
                        message_count = int(data[0]) if data and data[0] else 0
                        print(f"Folder contains {message_count} messages")
                        return True
                    else:
                        print(f"Failed to select '{folder_attempt}': {data}")
                except Exception as e:
                    print(f"Exception selecting '{folder_attempt}': {str(e)}")
                    continue
            
            # If all variations failed, list available folders to help troubleshoot
            print("All folder selection attempts failed. Listing available folders:")
            available_folders = self.list_folders()
            
            # For iCloud, try common alternative folder names
            if self.config.provider == 'icloud':
                alternative_folders = ['Sent', 'Sent Items', 'INBOX.Sent', 'INBOX/Sent']
                for alt_folder in alternative_folders:
                    if alt_folder in available_folders:
                        print(f"Trying alternative folder: {alt_folder}")
                        try:
                            status, data = self.connection.select(alt_folder)
                            if status == 'OK':
                                print(f"Successfully selected alternative folder: {alt_folder}")
                                # Update config for future use
                                self.config.sent_folder = alt_folder
                                message_count = int(data[0]) if data and data[0] else 0
                                print(f"Folder '{alt_folder}' contains {message_count} messages")
                                return True
                        except Exception as e:
                            print(f"Failed to select {alt_folder}: {str(e)}")
                            continue
            
            return False
            
            # Get folder message count
            message_count = int(data[0]) if data and data[0] else 0
            print(f"Successfully selected sent folder '{self.config.sent_folder}' with {message_count} messages")
            return True
            
        except Exception as e:
            print(f"Error selecting sent folder: {str(e)}")
            # If there's an error, try to list folders for troubleshooting
            print("Listing available folders to help troubleshoot:")
            self.list_folders()
            return False
    
    def disconnect(self) -> None:
        """
        Properly close IMAP connection and cleanup resources.
        """
        if self.connection and self.is_connected:
            try:
                # Only close if we have a selected folder (in SELECTED state)
                # Check current state to avoid "CLOSE illegal in state AUTH" error
                try:
                    # Try to close - this will only work if we're in SELECTED state
                    self.connection.close()
                except imaplib.IMAP4.error as e:
                    # If close fails, we're probably in AUTH state (no folder selected)
                    # This is fine, we can proceed to logout
                    pass
                
                # Logout from server
                self.connection.logout()
                print("IMAP connection closed successfully")
            except Exception as e:
                print(f"Warning: Error during disconnect: {str(e)}")
            finally:
                self.connection = None
                self.is_connected = False
    
    def __enter__(self):
        """Context manager entry"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - ensures cleanup"""
        self.disconnect()
    
    def fetch_message_uids(self, batch_size: int = 500) -> Iterator[List[str]]:
        """
        Fetch message UIDs in batches to prevent memory overflow.
        
        Args:
            batch_size: Number of messages to fetch per batch (default: 500)
            
        Yields:
            List[str]: Batch of message UIDs
        """
        if not self.is_connected or not self.connection:
            print("Error: Not connected to IMAP server")
            return
        
        max_search_retries = 2  # Retry search operation once on timeout
        
        for search_attempt in range(max_search_retries):
            try:
                # Search for all messages in the selected folder using UID search
                print("Searching for all messages in sent folder...")
                status, data = self.connection.uid('search', None, 'ALL')
                
                if status != 'OK':
                    print(f"Error: Failed to search messages: {data}")
                    return
                
                # Parse UIDs from search results
                if not data or not data[0]:
                    print("No messages found in sent folder")
                    return
                
                # Split the UID string into individual UIDs
                all_uids = data[0].decode('utf-8').split()
                total_messages = len(all_uids)
                
                print(f"Found {total_messages} messages in sent folder")
                
                # Yield UIDs in batches
                for i in range(0, total_messages, batch_size):
                    batch_uids = all_uids[i:i + batch_size]
                    batch_num = (i // batch_size) + 1
                    total_batches = (total_messages + batch_size - 1) // batch_size
                    
                    print(f"Processing batch {batch_num}/{total_batches} ({len(batch_uids)} messages)")
                    yield batch_uids
                
                return  # Success, exit retry loop
                
            except (imaplib.IMAP4.error, OSError, TimeoutError) as e:
                error_msg = f"Error fetching message UIDs: {str(e)}"
                if search_attempt == max_search_retries - 1:
                    print(f"Error: {error_msg} - maximum retries exceeded")
                    return
                else:
                    print(f"Warning: {error_msg} - retrying search operation...")
                    time.sleep(2)  # Wait 2 seconds before retry
                    continue
            except Exception as e:
                print(f"Error fetching message UIDs: {str(e)}")
                return
    
    def fetch_message(self, uid: str) -> Optional[email.message.Message]:
        """
        Fetch a single email message by UID with timeout handling and retry logic.
        
        Args:
            uid: Message UID to fetch
            
        Returns:
            email.message.Message: Parsed email message or None if error
        """
        if not self.is_connected or not self.connection:
            print(f"Error: Not connected to IMAP server for UID {uid}")
            return None
        
        max_fetch_retries = 2  # Retry individual fetch once on timeout
        
        for fetch_attempt in range(max_fetch_retries):
            try:
                # Fetch message by UID
                status, data = self.connection.uid('fetch', uid, '(RFC822)')
                
                if status != 'OK':
                    if fetch_attempt == max_fetch_retries - 1:
                        print(f"Warning: Failed to fetch message UID {uid}: {data}")
                    else:
                        print(f"Warning: Failed to fetch message UID {uid}: {data} - retrying...")
                        time.sleep(1)
                        continue
                    return None
                
                if not data or not data[0]:
                    print(f"Warning: No data returned for message UID {uid}")
                    return None
                
                # Parse the raw email message
                raw_email = data[0][1]
                if raw_email is None:
                    print(f"Warning: No email data returned for UID {uid}")
                    return None
                    
                if isinstance(raw_email, bytes):
                    message = email.message_from_bytes(raw_email)
                else:
                    message = email.message_from_string(str(raw_email))
                
                return message
                
            except (imaplib.IMAP4.error, OSError, TimeoutError) as e:
                error_msg = f"Timeout/connection error fetching message UID {uid}: {str(e)}"
                if fetch_attempt == max_fetch_retries - 1:
                    print(f"Error: {error_msg} - maximum retries exceeded")
                    return None
                else:
                    print(f"Warning: {error_msg} - retrying fetch...")
                    time.sleep(1)
                    continue
            except Exception as e:
                print(f"Error fetching message UID {uid}: {str(e)}")
                return None
        
        return None


class ContentProcessor:
    """Handles email content extraction, cleaning, and filtering"""
    
    def __init__(self):
        # Configure html2text converter
        if HTML_PROCESSING_AVAILABLE:
            self.html_converter = html2text.HTML2Text()
            self.html_converter.ignore_links = True
            self.html_converter.ignore_images = True
            self.html_converter.ignore_emphasis = False
            self.html_converter.body_width = 0  # Don't wrap lines
            self.html_converter.unicode_snob = True
        else:
            self.html_converter = None
    
    def extract_body_content(self, message: email.message.Message) -> str:
        """
        Extract body content from email message, handling multipart messages.
        
        Args:
            message: Email message to extract content from
            
        Returns:
            str: Extracted and cleaned body content
        """
        try:
            body_content = ""
            
            if message.is_multipart():
                # Handle multipart messages - prioritize text/plain, fallback to text/html
                text_parts = []
                html_parts = []
                
                for part in message.walk():
                    content_type = part.get_content_type()
                    content_disposition = str(part.get("Content-Disposition", ""))
                    
                    # Skip attachments
                    if "attachment" in content_disposition:
                        continue
                    
                    try:
                        payload = part.get_payload(decode=True)
                        if payload is None:
                            continue
                            
                        # Decode bytes to string
                        if isinstance(payload, bytes):
                            # Try to get charset from content type
                            charset = part.get_content_charset() or 'utf-8'
                            try:
                                text_content = payload.decode(charset)
                            except (UnicodeDecodeError, LookupError):
                                # Fallback to utf-8 with error handling
                                text_content = payload.decode('utf-8', errors='ignore')
                        else:
                            text_content = str(payload)
                        
                        # Collect text and HTML parts
                        if content_type == "text/plain":
                            text_parts.append(text_content)
                        elif content_type == "text/html":
                            html_parts.append(text_content)
                            
                    except Exception as e:
                        print(f"Warning: Error processing message part: {str(e)}")
                        continue
                
                # Prefer plain text over HTML
                if text_parts:
                    body_content = "\n\n".join(text_parts)
                elif html_parts:
                    # Convert HTML to text
                    html_content = "\n\n".join(html_parts)
                    body_content = self.convert_html_to_text(html_content)
                    
            else:
                # Handle single-part messages
                payload = message.get_payload(decode=True)
                if payload is not None:
                    # Decode bytes to string
                    if isinstance(payload, bytes):
                        charset = message.get_content_charset() or 'utf-8'
                        try:
                            body_content = payload.decode(charset)
                        except (UnicodeDecodeError, LookupError):
                            body_content = payload.decode('utf-8', errors='ignore')
                    else:
                        body_content = str(payload)
                    
                    # If it's HTML content, convert to text
                    content_type = message.get_content_type()
                    if content_type == "text/html":
                        body_content = self.convert_html_to_text(body_content)
            
            # Clean and normalize the extracted content
            if body_content:
                body_content = self.strip_quoted_replies(body_content)
                body_content = self.strip_opening_greetings(body_content)
                body_content = self.strip_signatures(body_content)
                body_content = self.normalize_whitespace(body_content)
            
            return body_content
            
        except Exception as e:
            print(f"Error extracting body content: {str(e)}")
            return ""
    
    def convert_html_to_text(self, html_content: str) -> str:
        """
        Convert HTML content to plain text using html2text and BeautifulSoup.
        
        Args:
            html_content: HTML content to convert
            
        Returns:
            str: Plain text content
        """
        if not html_content or not html_content.strip():
            return ""
        
        try:
            # First, use BeautifulSoup for robust HTML parsing and cleanup
            if HTML_PROCESSING_AVAILABLE:
                soup = BeautifulSoup(html_content, 'html.parser')
                
                # Remove script and style elements
                for script in soup(["script", "style"]):
                    script.decompose()
                
                # Get cleaned HTML
                cleaned_html = str(soup)
                
                # Convert to text using html2text
                if self.html_converter:
                    text_content = self.html_converter.handle(cleaned_html)
                else:
                    # Fallback: use BeautifulSoup's get_text method
                    text_content = soup.get_text()
            else:
                # Fallback: basic HTML tag removal using regex
                text_content = re.sub(r'<[^>]+>', '', html_content)
            
            return text_content
            
        except Exception as e:
            print(f"Warning: Error converting HTML to text: {str(e)}")
            # Fallback: basic HTML tag removal
            try:
                return re.sub(r'<[^>]+>', '', html_content)
            except Exception:
                return html_content
    
    def strip_quoted_replies(self, content: str) -> str:
        """
        Strip quoted replies and forwarded text from email content using comprehensive regex patterns.
        
        Args:
            content: Email content to clean
            
        Returns:
            str: Content with quoted replies removed
        """
        if not content:
            return ""
        
        try:
            lines = content.split('\n')
            cleaned_lines = []
            
            # Comprehensive patterns for quoted replies and forwards
            quote_patterns = [
                # Basic quote patterns
                r'^>.*',  # Lines starting with >
                r'^\s*>.*',  # Lines starting with whitespace and >
                r'^\s*>\s*>.*',  # Multiple levels of quoting
                
                # "On ... wrote:" patterns (various formats)
                r'^On .* wrote:.*',  # "On [date] [person] wrote:"
                r'^On .* at .* wrote:.*',  # "On [date] at [time] [person] wrote:"
                r'^On .*, .* wrote:.*',  # "On [day], [date] [person] wrote:"
                r'^\d{1,2}/\d{1,2}/\d{2,4}.*wrote:.*',  # Date formats with "wrote:"
                r'^\w+,\s+\w+\s+\d+,\s+\d{4}.*wrote:.*',  # "Monday, January 15, 2024 ... wrote:"
                
                # Email header patterns (forwards and replies)
                r'^From:.*',  # Email headers in forwards
                r'^To:.*',
                r'^Cc:.*',
                r'^Bcc:.*',
                r'^Subject:.*',
                r'^Date:.*',
                r'^Sent:.*',
                r'^Reply-To:.*',
                
                # Outlook-style patterns
                r'^\s*-----Original Message-----.*',  # Outlook original message
                r'^\s*________________________________.*',  # Outlook separator line
                r'^\s*From: .*',  # Forward headers with spacing
                r'^\s*Sent: .*',
                r'^\s*To: .*',
                r'^\s*Subject: .*',
                r'^\s*Date: .*',
                
                # Gmail-style patterns
                r'^\s*On .* <.*@.*> wrote:.*',  # Gmail "On [date] <email> wrote:"
                r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2} GMT.*wrote:.*',  # Gmail timestamp format
                
                # Apple Mail patterns
                r'^Begin forwarded message:.*',  # Apple Mail forward
                r'^Forwarded message:.*',
                r'^Message forwarded.*',
                
                # Other common patterns
                r'^\s*\[.*\] wrote:.*',  # [Name] wrote:
                r'^\s*<.*@.*> wrote:.*',  # <email@domain.com> wrote:
                r'^\s*".*" <.*@.*> wrote:.*',  # "Name" <email> wrote:
                
                # Signature separators
                r'^\s*--\s*$',  # Standard signature separator
                r'^\s*---+\s*$',  # Dash separators
                
                # Mobile email patterns
                r'^Sent from my .*',  # "Sent from my iPhone/Android"
                r'^Get Outlook for .*',  # Outlook mobile signature
                
                # International patterns
                r'.*\s+schrieb:.*',  # German "wrote"
                r'.*\s+escribió:.*',  # Spanish "wrote"
                r'.*\s+écrit:.*',  # French "wrote"
                r'.*\s+scrisse:.*',  # Italian "wrote"
            ]
            
            # Compile patterns for efficiency
            compiled_patterns = [re.compile(pattern, re.IGNORECASE) for pattern in quote_patterns]
            
            # Additional patterns to detect start of quoted sections
            quote_start_patterns = [
                re.compile(r'^\s*[-=_]{3,}\s*$'),  # Lines with multiple dashes/equals/underscores
                re.compile(r'^\s*\*{3,}\s*$'),     # Lines with multiple asterisks
                re.compile(r'^\s*#{3,}\s*$'),      # Lines with multiple hash symbols
            ]
            
            in_quoted_section = False
            consecutive_empty_lines = 0
            
            for i, line in enumerate(lines):
                # Check if this line starts a quoted section
                is_quote_line = any(pattern.match(line) for pattern in compiled_patterns)
                is_separator_line = any(pattern.match(line) for pattern in quote_start_patterns)
                
                # Track consecutive empty lines
                if not line.strip():
                    consecutive_empty_lines += 1
                else:
                    consecutive_empty_lines = 0
                
                # Start quoted section if we hit a quote pattern or separator
                if is_quote_line or is_separator_line:
                    in_quoted_section = True
                    continue
                
                # Handle quoted section logic
                if in_quoted_section:
                    # If we hit multiple empty lines, we might be out of the quoted section
                    if consecutive_empty_lines >= 1:  # Reduced from 2 to 1 for better detection
                        # Look ahead to see if the next non-empty line looks like original content
                        next_content_line = None
                        for j in range(i + 1, len(lines)):
                            if lines[j].strip():
                                next_content_line = lines[j]
                                break
                        
                        if next_content_line:
                            # Check if the next line looks like original content
                            is_next_quote = any(pattern.match(next_content_line) for pattern in compiled_patterns)
                            if not is_next_quote and len(next_content_line.strip()) > 5:  # Reduced threshold
                                # Looks like we're back to original content
                                in_quoted_section = False
                    
                    # If we're still in quoted section, check if this line should be kept
                    if in_quoted_section:
                        # Check if this line looks like original content
                        if (line.strip() and 
                            len(line.strip()) > 10 and 
                            not any(pattern.match(line) for pattern in compiled_patterns) and
                            not re.match(r'^\s*(From|To|Subject|Date|Sent|Cc|Bcc):', line, re.IGNORECASE) and
                            not line.strip().startswith('>')):  # Don't keep lines that start with >
                            # This might be original content mixed in, keep it
                            in_quoted_section = False
                        else:
                            continue
                
                # If we're not in a quoted section, keep the line
                if not in_quoted_section:
                    cleaned_lines.append(line)
            
            # Join lines and do a final cleanup pass
            result = '\n'.join(cleaned_lines)
            
            # Remove any remaining quoted blocks that might have been missed
            # Look for patterns like "On ... wrote:" followed by indented content
            result = re.sub(r'\n\s*On\s+.*wrote:\s*\n(.*\n)*?(?=\n\S|\n*$)', '\n', result, flags=re.IGNORECASE | re.MULTILINE)
            
            # Remove forwarded message blocks
            result = re.sub(r'\n\s*-+\s*Forwarded message\s*-+.*?\n(.*\n)*?(?=\n\S|\n*$)', '\n', result, flags=re.IGNORECASE | re.MULTILINE)
            
            return result
            
        except Exception as e:
            print(f"Warning: Error stripping quoted replies: {str(e)}")
            return content
    
    def strip_opening_greetings(self, content: str) -> str:
        """
        Strip opening greetings from email content.
        
        Args:
            content: Email content to clean
            
        Returns:
            str: Content with opening greetings removed
        """
        if not content:
            return ""
        
        try:
            lines = content.split('\n')
            cleaned_lines = []
            greeting_found = False
            
            # Patterns for opening greetings - more precise patterns
            greeting_patterns = [
                # Standard greetings with names (ensure they end the line after name/punctuation)
                r'^(Hi|Hello|Hey|Dear)\s+[A-Za-z][A-Za-z\s\'.-]*[,:]?\s*$',  # Hi Krishna, Hello Ben, Dear Raina
                
                # Formal greetings
                r'^Dear\s+(Sir|Madam|Sir\s+or\s+Madam)[,:]?\s*$',  # Dear Sir or Madam
                r'^To\s+whom\s+it\s+may\s+concern[,:]?\s*$',  # To whom it may concern
                
                # Group greetings
                r'^(Hi|Hello|Hey)\s+(all|everyone|team|folks|guys)[,:]?\s*$',  # Hi all, Hello everyone
                r'^(Hi|Hello|Hey)\s+there[,:!.]?\s*$',  # Hi there
                
                # Time-based greetings
                r'^(Good\s+morning|Good\s+afternoon|Good\s+evening)[,:]?\s*$',
                r'^(Good\s+morning|Good\s+afternoon|Good\s+evening)\s+[A-Za-z][A-Za-z\s\'.-]*[,:]?\s*$',
                
                # Simple greetings
                r'^(Hi|Hello|Hey)[,:]?\s*$',  # Just "Hi," or "Hello"
                
                # Multiple name greetings
                r'^(Hi|Hello|Hey|Dear)\s+[A-Za-z][A-Za-z\s\'.-]*(\s+and\s+[A-Za-z][A-Za-z\s\'.-]*)+[,:]?\s*$',  # Hi John and Jane
            ]
            
            # Compile patterns for efficiency
            compiled_greeting_patterns = [re.compile(pattern, re.IGNORECASE) for pattern in greeting_patterns]
            
            # Process lines and remove greeting lines at the very beginning only
            for i, line in enumerate(lines):
                line_stripped = line.strip()
                
                # Only check for greetings in the first few non-empty lines
                if i < 3 and line_stripped:  # Only check first 3 non-empty lines for greetings
                    is_greeting = any(pattern.match(line_stripped) for pattern in compiled_greeting_patterns)
                    if is_greeting:
                        greeting_found = True
                        continue  # Skip greeting lines
                    elif greeting_found:
                        # If we already found a greeting and this line is not a greeting, 
                        # we're done with greeting removal
                        pass
                
                # Keep all other lines
                cleaned_lines.append(line)
            
            return '\n'.join(cleaned_lines)
            
        except Exception as e:
            print(f"Warning: Error stripping opening greetings: {str(e)}")
            return content
    
    def strip_signatures(self, content: str) -> str:
        """
        Strip signatures from email content, including Kevin Lin's specific signature.
        
        Args:
            content: Email content to clean
            
        Returns:
            str: Content with signatures removed
        """
        if not content:
            return ""
        
        try:
            lines = content.split('\n')
            cleaned_lines = []
            
            # Patterns for signature detection
            signature_patterns = [
                # Kevin Lin's specific signature patterns
                r'^(Best\s+regards|Sincerely\s+yours|Regards|Sincerely)[,:]?\s*$',
                r'^Kevin\s+Lin\s*$',
                r'^Lin\s+Yun\s*$',
                
                # Common signature closings
                r'^(Best|Regards|Thanks|Thank\s+you|Cheers|Yours\s+truly|Yours\s+sincerely)[,:]?\s*$',
                r'^(Kind\s+regards|Warm\s+regards|With\s+regards)[,:]?\s*$',
                r'^(Best\s+wishes|Many\s+thanks|Thank\s+you\s+very\s+much)[,:]?\s*$',
                
                # Signature separators
                r'^\s*--\s*$',  # Standard signature separator
                r'^\s*---+\s*$',  # Multiple dashes
                r'^\s*_{3,}\s*$',  # Multiple underscores
                
                # Mobile signatures
                r'^Sent\s+from\s+my\s+.*$',  # Sent from my iPhone/Android
                r'^Get\s+Outlook\s+for\s+.*$',  # Get Outlook for iOS/Android
                
                # Name-like patterns (common names that might be signatures)
                r'^[A-Z][a-z]+\s+[A-Z][a-z]+\s*$',  # First Last
                r'^[A-Z][a-z]+\s+[A-Z]\.\s+[A-Z][a-z]+\s*$',  # First M. Last
                r'^[A-Z]\.\s+[A-Z][a-z]+\s*$',  # F. Last
            ]
            
            # Compile patterns for efficiency
            compiled_signature_patterns = [re.compile(pattern, re.IGNORECASE) for pattern in signature_patterns]
            
            # Work backwards from the end to detect signature blocks
            signature_start_index = len(lines)
            
            # Look for signature patterns starting from the end
            for i in range(len(lines) - 1, -1, -1):
                line = lines[i].strip()
                
                # Skip empty lines
                if not line:
                    continue
                
                # Check if this line matches a signature pattern
                is_signature_line = any(pattern.match(line) for pattern in compiled_signature_patterns)
                
                if is_signature_line:
                    # Found a signature line, mark this as potential signature start
                    signature_start_index = i
                    
                    # Look for preceding signature lines (like "Best regards" followed by "Kevin Lin")
                    # Continue checking previous lines for related signature content
                    for j in range(i - 1, max(0, i - 5), -1):  # Check up to 5 lines before
                        prev_line = lines[j].strip()
                        if not prev_line:
                            continue  # Skip empty lines
                        
                        # Check if previous line is also part of signature
                        is_prev_signature = any(pattern.match(prev_line) for pattern in compiled_signature_patterns)
                        if is_prev_signature:
                            signature_start_index = j
                        else:
                            break  # Stop if we hit non-signature content
                    
                    break  # Found signature block, stop searching
                else:
                    # If we hit substantial content (more than 10 words), stop looking for signatures
                    words = line.split()
                    if len(words) > 10:
                        break
            
            # Keep only lines before the signature
            cleaned_lines = lines[:signature_start_index]
            
            # Remove trailing empty lines
            while cleaned_lines and not cleaned_lines[-1].strip():
                cleaned_lines.pop()
            
            return '\n'.join(cleaned_lines)
            
        except Exception as e:
            print(f"Warning: Error stripping signatures: {str(e)}")
            return content
    
    def normalize_whitespace(self, content: str) -> str:
        """
        Normalize whitespace and standardize line breaks, removing blank lines.
        
        Args:
            content: Content to normalize
            
        Returns:
            str: Content with normalized whitespace and blank lines removed
        """
        if not content:
            return ""
        
        try:
            # Replace different types of line breaks with standard \n
            content = re.sub(r'\r\n|\r', '\n', content)
            
            # Remove excessive whitespace while preserving paragraph structure
            # Replace multiple spaces with single space
            content = re.sub(r'[ \t]+', ' ', content)
            
            # Remove leading/trailing whitespace from each line
            lines = content.split('\n')
            cleaned_lines = [line.strip() for line in lines]
            
            # Remove all blank lines as requested
            cleaned_lines = [line for line in cleaned_lines if line]
            
            # Join lines back together with single newlines
            content = '\n'.join(cleaned_lines)
            
            return content
            
        except Exception as e:
            print(f"Warning: Error normalizing whitespace: {str(e)}")
            return content.strip() if content else ""
    
    def is_valid_content(self, content: str) -> bool:
        """
        Validate that content meets minimum quality requirements for meaningful email detection.
        
        Args:
            content: Content to validate
            
        Returns:
            bool: True if content is valid, False otherwise
        """
        if not content or not content.strip():
            return False
        
        try:
            # Clean content for analysis
            cleaned_content = content.strip()
            
            # Count words (split by whitespace and filter out empty strings)
            words = [word for word in cleaned_content.split() if word.strip()]
            word_count = len(words)
            
            # Requirement 3.1: minimum 20 words
            if word_count < 20:
                return False
            
            # Additional quality checks for meaningful content detection
            
            # Check if content is mostly non-alphabetic (might be encoded/corrupted)
            alpha_chars = sum(1 for c in cleaned_content if c.isalpha())
            total_chars = len(cleaned_content.replace(' ', '').replace('\n', '').replace('\t', ''))
            
            if total_chars > 0:
                alpha_ratio = alpha_chars / total_chars
                # Require at least 40% alphabetic characters (lowered from 50% to be less strict)
                if alpha_ratio < 0.4:
                    return False
            
            # Check for minimum sentence structure
            # Look for basic punctuation that indicates proper sentences
            sentence_endings = sum(1 for c in cleaned_content if c in '.!?')
            if sentence_endings == 0 and word_count > 50:
                # Long content without any sentence endings might be corrupted
                return False
            
            # Check for excessive repetition (might indicate spam or corrupted content)
            if word_count >= 10:
                # Count unique words vs total words
                unique_words = set(word.lower() for word in words if len(word) > 2)  # Ignore short words
                if len(unique_words) > 0:
                    uniqueness_ratio = len(unique_words) / len([w for w in words if len(w) > 2])
                    # If less than 30% of words are unique, might be spam or repetitive content
                    if uniqueness_ratio < 0.3:
                        return False
            
            # Check for common spam/system patterns in content
            spam_patterns = [
                r'click here',
                r'unsubscribe',
                r'viagra',
                r'casino',
                r'lottery',
                r'winner',
                r'congratulations.*won',
                r'urgent.*action.*required',
                r'verify.*account.*immediately',
            ]
            
            content_lower = cleaned_content.lower()
            spam_matches = sum(1 for pattern in spam_patterns if re.search(pattern, content_lower))
            
            # If multiple spam patterns match, likely not meaningful personal content
            if spam_matches >= 2:
                return False
            
            # Check for minimum content diversity
            # Content should have a mix of different word lengths
            if word_count >= 20:
                word_lengths = [len(word) for word in words]
                avg_word_length = sum(word_lengths) / len(word_lengths)
                
                # Very short average word length might indicate corrupted content
                if avg_word_length < 2.5:
                    return False
                
                # Very long average word length might indicate encoded content
                if avg_word_length > 15:
                    return False
            
            return True
            
        except Exception as e:
            print(f"Warning: Error validating content: {str(e)}")
            return False
    
    def is_system_generated(self, message: email.message.Message) -> bool:
        """
        Check if message appears to be system-generated (auto-replies, receipts, etc.).
        
        Args:
            message: Email message to check
            
        Returns:
            bool: True if message appears to be system-generated
        """
        try:
            # Check common system-generated message indicators
            subject = message.get('Subject', '').lower()
            
            # Enhanced system message patterns for comprehensive detection
            system_patterns = [
                # Auto-replies and out of office
                r'auto.?reply',
                r'automatic.*reply',
                r'out of office',
                r'vacation.*message',
                r'away.*message',
                r'absence.*notification',
                r'currently.*unavailable',
                
                # Delivery notifications and bounces
                r'delivery.*notification',
                r'delivery.*status.*notification',
                r'undelivered.*mail',
                r'mail.*delivery.*failed',
                r'message.*undeliverable',
                r'bounce.*message',
                r'returned.*mail',
                r'mail.*system.*error',
                
                # Read receipts and confirmations
                r'read.*receipt',
                r'delivery.*receipt',
                r'message.*receipt',
                r'confirmation.*receipt',
                
                # System daemons and postmaster
                r'mailer.?daemon',
                r'postmaster',
                r'mail.*administrator',
                
                # No-reply patterns
                r'no.?reply',
                r'do.?not.?reply',
                r'donot.*reply',
                
                # Calendar and meeting notifications
                r'meeting.*invitation',
                r'calendar.*notification',
                r'appointment.*reminder',
                r'event.*notification',
                
                # Security and system alerts
                r'security.*alert',
                r'password.*reset',
                r'account.*notification',
                r'system.*notification',
                r'service.*notification',
                
                # Subscription and newsletter patterns (only if combined with other indicators)
                # r'unsubscribe',  # Commented out as it's too broad
                # r'newsletter',   # Commented out as it's too broad  
                # r'mailing.*list', # Commented out as it's too broad
                
                # Error messages
                r'error.*report',
                r'failure.*notification',
                r'warning.*message',
            ]
            
            # Check subject line against all patterns
            for pattern in system_patterns:
                if re.search(pattern, subject, re.IGNORECASE):
                    return True
            
            # Check sender/from field for system addresses
            from_field = message.get('From', '').lower()
            system_senders = [
                'mailer-daemon',
                'postmaster',
                'noreply',
                'no-reply',
                'donotreply',
                'do-not-reply',
                'bounce',
                'auto-reply',
                'autoreply',
                'system',
                'admin',
                'administrator',
                'notification',
                'alerts',
                'security',
                'support',
            ]
            
            for sender in system_senders:
                if sender in from_field:
                    return True
            
            # Check for auto-reply and system headers
            auto_reply_headers = [
                'X-Autoreply',
                'X-Autorespond',
                'Auto-Submitted',
                'X-Auto-Response-Suppress',
                'X-Mailer-Daemon',
                'X-Failed-Recipients',
                'X-Delivery-Status',
            ]
            
            for header in auto_reply_headers:
                header_value = message.get(header)
                if header_value:
                    # Special handling for Auto-Submitted header
                    if header == 'Auto-Submitted' and header_value.lower() != 'no':
                        return True
                    elif header != 'Auto-Submitted':
                        return True
            
            # Check message body for system-generated patterns
            try:
                # Get a sample of the message body to check for system patterns
                body_sample = ""
                if message.is_multipart():
                    for part in message.walk():
                        if part.get_content_type() == "text/plain":
                            payload = part.get_payload(decode=True)
                            if payload:
                                if isinstance(payload, bytes):
                                    charset = part.get_content_charset() or 'utf-8'
                                    try:
                                        body_sample = payload.decode(charset)[:500]  # First 500 chars
                                    except (UnicodeDecodeError, LookupError):
                                        body_sample = payload.decode('utf-8', errors='ignore')[:500]
                                break
                else:
                    payload = message.get_payload(decode=True)
                    if payload and isinstance(payload, bytes):
                        charset = message.get_content_charset() or 'utf-8'
                        try:
                            body_sample = payload.decode(charset)[:500]
                        except (UnicodeDecodeError, LookupError):
                            body_sample = payload.decode('utf-8', errors='ignore')[:500]
                
                # Check body for system-generated content patterns
                if body_sample:
                    body_patterns = [
                        r'this.*is.*an.*automatic.*message',
                        r'do.*not.*reply.*to.*this.*message',
                        r'this.*message.*was.*automatically.*generated',
                        r'undelivered.*mail.*returned.*to.*sender',
                        r'delivery.*status.*notification',
                        r'out.*of.*office.*auto.*reply',
                    ]
                    
                    for pattern in body_patterns:
                        if re.search(pattern, body_sample.lower(), re.IGNORECASE):
                            return True
                            
            except Exception:
                # If body checking fails, continue with other checks
                pass
            
            return False
            
        except Exception as e:
            print(f"Warning: Error checking if message is system-generated: {str(e)}")
            return False
    
    def hash_content(self, content: str) -> str:
        """
        Generate a SHA-256 hash of normalized content for duplicate detection.
        
        Args:
            content: Content to hash
            
        Returns:
            str: SHA-256 hash of the content
        """
        if not content:
            return ""
        
        try:
            # Normalize content before hashing to ensure consistent comparison
            normalized_content = self.normalize_whitespace(content)
            
            # Convert to lowercase and remove extra whitespace for better duplicate detection
            # This helps catch duplicates that might have minor formatting differences
            content_for_hashing = re.sub(r'\s+', ' ', normalized_content.lower().strip())
            
            # Check if content is empty after normalization
            if not content_for_hashing:
                return ""
            
            # Generate SHA-256 hash
            content_bytes = content_for_hashing.encode('utf-8')
            hash_object = hashlib.sha256(content_bytes)
            content_hash = hash_object.hexdigest()
            
            return content_hash
            
        except Exception as e:
            print(f"Warning: Error hashing content: {str(e)}")
            return ""
    
    def is_content_duplicate(self, content: str, existing_hashes: Set[str]) -> bool:
        """
        Check if content is a duplicate based on content hash comparison.
        
        Args:
            content: Content to check for duplication
            existing_hashes: Set of existing content hashes
            
        Returns:
            bool: True if content is a duplicate, False otherwise
        """
        if not content or not content.strip():
            return False
        
        try:
            content_hash = self.hash_content(content)
            
            if not content_hash:
                return False
            
            return content_hash in existing_hashes
            
        except Exception as e:
            print(f"Warning: Error checking content duplicate: {str(e)}")
            return False


class CacheManager:
    """Manages UID caching and content hash tracking for duplicate prevention"""
    
    def __init__(self, provider: str, output_dir: str = "output"):
        """
        Initialize cache manager for the specified provider.
        
        Args:
            provider: Email provider ('gmail' or 'icloud')
            output_dir: Directory where cache files are stored
        """
        self.provider = provider.lower()
        self.output_dir = output_dir
        self.cache_file = os.path.join(output_dir, f"{self.provider}.cache.json")
        self.processed_uids: Set[str] = set()
        self.content_hashes: Set[str] = set()  # Add content hash tracking
        self.cache_metadata = {
            "last_updated": None,
            "total_processed": 0,
            "total_content_hashes": 0  # Add content hash count tracking
        }
        
        # Ensure output directory exists
        self._ensure_output_directory()
    
    def _ensure_output_directory(self) -> None:
        """Create output directory if it doesn't exist"""
        try:
            if not os.path.exists(self.output_dir):
                os.makedirs(self.output_dir)
                print(f"Created output directory: {self.output_dir}")
        except Exception as e:
            print(f"Warning: Failed to create output directory {self.output_dir}: {str(e)}")
    
    def load_cache(self) -> None:
        """
        Load existing cache data from JSON file.
        Creates new cache if file doesn't exist or is corrupted.
        """
        try:
            if os.path.exists(self.cache_file):
                print(f"Loading cache from {self.cache_file}")
                
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    cache_data = json.load(f)
                
                # Validate cache structure
                if not isinstance(cache_data, dict):
                    raise ValueError("Cache file has invalid structure")
                
                # Load processed UIDs
                processed_uids = cache_data.get('processed_uids', [])
                if isinstance(processed_uids, list):
                    self.processed_uids = set(processed_uids)
                else:
                    raise ValueError("processed_uids must be a list")
                
                # Load content hashes
                content_hashes = cache_data.get('content_hashes', [])
                if isinstance(content_hashes, list):
                    self.content_hashes = set(content_hashes)
                else:
                    raise ValueError("content_hashes must be a list")
                
                # Load metadata
                self.cache_metadata['last_updated'] = cache_data.get('last_updated')
                self.cache_metadata['total_processed'] = cache_data.get('total_processed', len(self.processed_uids))
                self.cache_metadata['total_content_hashes'] = cache_data.get('total_content_hashes', len(self.content_hashes))
                
                print(f"Loaded cache with {len(self.processed_uids)} processed UIDs and {len(self.content_hashes)} content hashes")
                if self.cache_metadata['last_updated']:
                    print(f"Cache last updated: {self.cache_metadata['last_updated']}")
                
            else:
                print(f"No existing cache found at {self.cache_file}")
                print("Starting with empty cache")
                
        except Exception as e:
            print(f"Warning: Error loading cache file {self.cache_file}: {str(e)}")
            print("Creating new cache file and continuing...")
            self._create_new_cache()
    
    def _create_new_cache(self) -> None:
        """Create a new empty cache"""
        self.processed_uids = set()
        self.content_hashes = set()
        self.cache_metadata = {
            "last_updated": None,
            "total_processed": 0,
            "total_content_hashes": 0
        }
        print("Initialized new empty cache")
    
    def save_cache(self) -> None:
        """
        Save current cache data to JSON file.
        Updates metadata with current timestamp and count.
        """
        try:
            # Update metadata
            self.cache_metadata['last_updated'] = datetime.datetime.now().isoformat()
            self.cache_metadata['total_processed'] = len(self.processed_uids)
            self.cache_metadata['total_content_hashes'] = len(self.content_hashes)
            
            # Prepare cache data
            cache_data = {
                'processed_uids': sorted(list(self.processed_uids)),  # Sort for consistency
                'content_hashes': sorted(list(self.content_hashes)), # Sort for consistency
                'last_updated': self.cache_metadata['last_updated'],
                'total_processed': self.cache_metadata['total_processed'],
                'total_content_hashes': self.cache_metadata['total_content_hashes']
            }
            
            # Write to file with atomic operation (write to temp file first)
            temp_file = self.cache_file + '.tmp'
            
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, indent=2, ensure_ascii=False)
            
            # Atomic move (rename temp file to actual file)
            if os.path.exists(self.cache_file):
                # Create backup of existing cache
                backup_file = self.cache_file + '.bak'
                if os.path.exists(backup_file):
                    os.remove(backup_file)
                os.rename(self.cache_file, backup_file)
            
            os.rename(temp_file, self.cache_file)
            
            print(f"Cache saved successfully to {self.cache_file}")
            print(f"Total cached UIDs: {len(self.processed_uids)}, Total content hashes: {len(self.content_hashes)}")
            
        except Exception as e:
            print(f"Error saving cache to {self.cache_file}: {str(e)}")
            # Clean up temp file if it exists
            temp_file = self.cache_file + '.tmp'
            if os.path.exists(temp_file):
                try:
                    os.remove(temp_file)
                except Exception:
                    pass
            raise
    
    def is_processed(self, uid: str) -> bool:
        """
        Check if a UID has been processed before.
        
        Args:
            uid: Message UID to check
            
        Returns:
            bool: True if UID is in cache, False otherwise
        """
        return uid in self.processed_uids
    
    def mark_processed(self, uid: str) -> None:
        """
        Mark a UID as processed by adding it to the cache.
        
        Args:
            uid: Message UID to mark as processed
        """
        self.processed_uids.add(uid)
    
    def is_content_duplicate(self, content_hash: str) -> bool:
        """
        Check if a content hash has been processed before.
        
        Args:
            content_hash: Content hash to check
            
        Returns:
            bool: True if content hash is in cache, False otherwise
        """
        return content_hash in self.content_hashes
    
    def add_content_hash(self, content_hash: str) -> None:
        """
        Add a content hash to the cache.
        
        Args:
            content_hash: Content hash to add to cache
        """
        if content_hash:  # Only add non-empty hashes
            self.content_hashes.add(content_hash)
    
    def get_content_hashes(self) -> Set[str]:
        """
        Get the set of all cached content hashes.
        
        Returns:
            Set[str]: Set of cached content hashes
        """
        return self.content_hashes.copy()
    
    def get_cache_stats(self) -> dict:
        """
        Get cache statistics.
        
        Returns:
            dict: Cache statistics including size and last updated
        """
        return {
            'total_cached_uids': len(self.processed_uids),
            'total_cached_content_hashes': len(self.content_hashes),
            'last_updated': self.cache_metadata['last_updated'],
            'cache_file': self.cache_file,
            'provider': self.provider
        }


class OutputWriter:
    """Handles file creation and content writing for processed emails"""
    
    def __init__(self, provider: str, output_dir: str = "output"):
        """
        Initialize OutputWriter for the specified provider.
        
        Args:
            provider: Email provider ('gmail' or 'icloud')
            output_dir: Directory where output files are stored
        """
        self.provider = provider.lower()
        self.output_dir = output_dir
        self.output_file = None
        self.file_handle = None
        self.email_count = 0
        
        # Ensure output directory exists
        self._ensure_output_directory()
        
        # Generate timestamped filename
        self._generate_output_filename()
    
    def _ensure_output_directory(self) -> None:
        """Create output directory if it doesn't exist"""
        try:
            if not os.path.exists(self.output_dir):
                os.makedirs(self.output_dir)
                print(f"Created output directory: {self.output_dir}")
        except Exception as e:
            raise Exception(f"Failed to create output directory {self.output_dir}: {str(e)}")
    
    def _generate_output_filename(self) -> None:
        """Generate timestamped filename in format: provider-yyyyMMdd-HHmmss.txt"""
        timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        filename = f"{self.provider}-{timestamp}.txt"
        self.output_file = os.path.join(self.output_dir, filename)
        print(f"Output file will be: {self.output_file}")
    
    def create_output_file(self) -> None:
        """Create and open the output file for writing"""
        try:
            self.file_handle = open(self.output_file, 'w', encoding='utf-8')
            print(f"Created output file: {self.output_file}")
        except Exception as e:
            raise Exception(f"Failed to create output file {self.output_file}: {str(e)}")
    
    def write_content(self, content: str, email_number: Optional[int] = None) -> None:
        """
        Write email content to the output file with proper formatting.
        
        Args:
            content: Cleaned email content to write
            email_number: Optional email number for delimiter
        """
        if not self.file_handle:
            raise Exception("Output file not created. Call create_output_file() first.")
        
        try:
            # Use provided email number or increment internal counter
            if email_number is None:
                self.email_count += 1
                email_number = self.email_count
            
            # Write email delimiter
            delimiter = f"=== EMAIL {email_number} ===\n"
            self.file_handle.write(delimiter)
            
            # Write cleaned content
            self.file_handle.write(content)
            
            # Ensure content ends with newlines for proper separation
            if not content.endswith('\n'):
                self.file_handle.write('\n')
            
            # Add blank line for readability
            self.file_handle.write('\n')
            
            # Flush to ensure content is written
            self.file_handle.flush()
            
        except Exception as e:
            raise Exception(f"Failed to write content to output file: {str(e)}")
    
    def finalize_output(self) -> None:
        """Close the output file and finalize writing"""
        if self.file_handle:
            try:
                self.file_handle.close()
                self.file_handle = None
                print(f"Output file finalized: {self.output_file}")
                print(f"Total emails written: {self.email_count}")
            except Exception as e:
                print(f"Warning: Error closing output file: {str(e)}")
    
    def get_output_filename(self) -> str:
        """Get the output filename"""
        return self.output_file
    
    def get_email_count(self) -> int:
        """Get the number of emails written to the output file"""
        return self.email_count


class EmailProcessor:
    """Handles email fetching, processing, and statistics tracking"""
    
    def __init__(self, imap_manager: IMAPConnectionManager, cache_manager: Optional[CacheManager] = None, output_writer: Optional[OutputWriter] = None):
        self.imap_manager = imap_manager
        self.stats = ProcessingStats()
        self.processed_messages = []  # Store processed messages for preview/summary
        self.content_processor = ContentProcessor()  # Initialize content processor
        self.cache_manager = cache_manager  # Cache manager for duplicate prevention
        self.output_writer = output_writer  # Output writer for file management
    
    def process_emails(self, batch_size: int = 500, progress_interval: int = 100) -> ProcessingStats:
        """
        Process all emails in the sent folder with pagination and progress logging.
        
        Args:
            batch_size: Number of messages to fetch per batch
            progress_interval: Log progress every N processed emails
            
        Returns:
            ProcessingStats: Final processing statistics
        """
        print("Starting email processing...")
        self.stats.start_processing()
        
        # Load existing cache if cache manager is available
        if self.cache_manager:
            try:
                self.cache_manager.load_cache()
                cache_stats = self.cache_manager.get_cache_stats()
                print(f"Cache loaded: {cache_stats['total_cached_uids']} previously processed UIDs, {cache_stats['total_cached_content_hashes']} content hashes")
            except Exception as e:
                print(f"Warning: Failed to load cache: {str(e)}")
                self.stats.increment_error_type('cache')
        
        # Create output file if output writer is available
        if self.output_writer:
            try:
                self.output_writer.create_output_file()
            except Exception as e:
                print(f"Error: Failed to create output file: {str(e)}")
                self.stats.increment_error_type('output')
                self.stats.end_processing()
                return self.stats
        
        try:
            # Process emails in batches with enhanced error handling
            batch_count = 0
            for batch_uids in self.imap_manager.fetch_message_uids(batch_size):
                batch_count += 1
                print(f"Starting batch {batch_count} processing...")
                
                try:
                    self._process_batch(batch_uids, progress_interval)
                    print(f"Completed batch {batch_count} - {self.stats.get_quick_stats()}")
                except Exception as e:
                    print(f"Error: Failed to process batch {batch_count}: {str(e)}")
                    self.stats.increment_error_type('processing')
                    # Continue with next batch instead of failing completely
                    continue
            
            # Finalize output file if output writer is available
            if self.output_writer:
                try:
                    self.output_writer.finalize_output()
                    print(f"Output file successfully written: {self.output_writer.get_output_filename()}")
                except Exception as e:
                    print(f"Warning: Failed to finalize output file: {str(e)}")
                    self.stats.increment_error_type('output')
            
            # Save cache after processing if cache manager is available
            if self.cache_manager:
                try:
                    self.cache_manager.save_cache()
                    print("Cache updated and saved successfully")
                except Exception as e:
                    print(f"Warning: Failed to save cache: {str(e)}")
                    self.stats.increment_error_type('cache')
            
            # Mark end of processing and show final summary
            self.stats.end_processing()
            print("\nEmail processing completed!")
            print(self.stats.get_summary())
            
            # Show preview of first 3 retained messages
            self._show_message_preview()
            
            return self.stats
            
        except Exception as e:
            print(f"Error: Critical failure during email processing: {str(e)}")
            self.stats.increment_error_type('processing')
            self.stats.end_processing()
            
            # Finalize output file even if there was an error
            if self.output_writer:
                try:
                    self.output_writer.finalize_output()
                    print("Output file finalized despite processing error")
                except Exception as output_error:
                    print(f"Warning: Failed to finalize output file after error: {str(output_error)}")
                    self.stats.increment_error_type('output')
            
            # Try to save cache even if there was an error
            if self.cache_manager:
                try:
                    self.cache_manager.save_cache()
                    print("Cache saved despite processing error")
                except Exception as cache_error:
                    print(f"Warning: Failed to save cache after error: {str(cache_error)}")
                    self.stats.increment_error_type('cache')
            
            return self.stats
    
    def _process_batch(self, uids: List[str], progress_interval: int) -> None:
        """
        Process a batch of message UIDs sequentially with enhanced error handling.
        
        Args:
            uids: List of message UIDs to process
            progress_interval: Log progress every N processed emails
        """
        batch_start_time = datetime.datetime.now()
        
        for uid in uids:
            try:
                # Check if message is already processed using cache
                if self.cache_manager and self.cache_manager.is_processed(uid):
                    self.stats.skipped_duplicate += 1
                    continue
                
                # Fetch individual message with timeout handling
                try:
                    message = self.imap_manager.fetch_message(uid)
                except (TimeoutError, OSError) as e:
                    print(f"Warning: Timeout/connection error for UID {uid}: {str(e)}")
                    self.stats.increment_error_type('timeout')
                    continue
                except Exception as e:
                    print(f"Warning: Fetch error for UID {uid}: {str(e)}")
                    self.stats.increment_error_type('fetch')
                    continue
                
                if message is None:
                    self.stats.increment_error_type('fetch')
                    continue
                
                # Process the message and check if it was retained
                try:
                    was_retained = self._process_single_message(uid, message)
                    
                    # Only mark message as processed in cache if it was actually retained
                    if self.cache_manager and was_retained:
                        self.cache_manager.mark_processed(uid)
                except Exception as e:
                    print(f"Warning: Processing error for UID {uid}: {str(e)}")
                    self.stats.increment_error_type('processing')
                    continue
                
                # Update total count
                self.stats.total_fetched += 1
                
                # Enhanced progress logging at specified intervals
                if self.stats.total_fetched % progress_interval == 0:
                    batch_duration = datetime.datetime.now() - batch_start_time
                    rate = progress_interval / batch_duration.total_seconds() if batch_duration.total_seconds() > 0 else 0
                    print(f"Progress: {self.stats.get_quick_stats()} (processing rate: {rate:.1f} emails/sec)")
                
            except Exception as e:
                print(f"Error: Unexpected error processing message UID {uid}: {str(e)}")
                self.stats.increment_error_type('processing')
                continue
    
    def _process_single_message(self, uid: str, message: email.message.Message) -> bool:
        """
        Process a single email message with content extraction and filtering.
        
        Args:
            uid: Message UID
            message: Parsed email message
            
        Returns:
            bool: True if message was retained, False if filtered out
        """
        try:
            # Check if message is system-generated first
            if self.content_processor.is_system_generated(message):
                self.stats.skipped_system += 1
                return False
            
            # Extract and clean body content
            body_content = self.content_processor.extract_body_content(message)
            
            # Validate content quality
            if not self.content_processor.is_valid_content(body_content):
                self.stats.skipped_short += 1
                return False
            
            # Check for content-based duplicates
            if self.cache_manager:
                existing_hashes = self.cache_manager.get_content_hashes()
                if self.content_processor.is_content_duplicate(body_content, existing_hashes):
                    self.stats.skipped_duplicate += 1
                    content_hash = self.content_processor.hash_content(body_content)
                    print(f"Skipping duplicate content (hash: {content_hash[:8]}...)")
                    return False
            
            # Get basic message info
            subject = message.get('Subject', 'No Subject')
            date = message.get('Date', 'No Date')
            
            # Store processed message with cleaned content for preview
            self.stats.retained += 1
            self.processed_messages.append({
                'uid': uid,
                'subject': subject,
                'date': date,
                'content': body_content,
                'word_count': len(body_content.split())
            })
            
            # Write content to output file if output writer is available
            if self.output_writer:
                try:
                    self.output_writer.write_content(body_content)
                except Exception as e:
                    print(f"Warning: Failed to write email content to output file: {str(e)}")
                    self.stats.increment_error_type('output')
                    # Don't fail processing for output errors, just log and continue
            
            # Add content hash to cache for future duplicate detection
            if self.cache_manager:
                try:
                    content_hash = self.content_processor.hash_content(body_content)
                    if content_hash:
                        self.cache_manager.add_content_hash(content_hash)
                except Exception as e:
                    print(f"Warning: Failed to cache content hash: {str(e)}")
                    self.stats.increment_error_type('cache')
            
            return True  # Message was retained
                
        except Exception as e:
            print(f"Error: Failed to process message content for UID {uid}: {str(e)}")
            self.stats.increment_error_type('processing')
            return False  # Message was not retained due to error
    
    def _show_message_preview(self) -> None:
        """Show enhanced preview of first 3 retained messages for quality check"""
        if not self.processed_messages:
            print("\nNo messages retained for preview.")
            return
        
        preview_count = min(3, len(self.processed_messages))
        print(f"\nPreview of first {preview_count} retained message(s):")
        print("=" * 80)
        
        for i, message in enumerate(self.processed_messages[:preview_count], 1):
            print(f"\nMessage {i}:")
            print(f"  UID: {message['uid']}")
            print(f"  Subject: {message['subject']}")
            print(f"  Date: {message['date']}")
            print(f"  Word count: {message['word_count']}")
            print(f"  Content preview (first 200 characters):")
            
            # Show first 200 characters of content with proper line breaks
            content_preview = message['content'][:200]
            if len(message['content']) > 200:
                content_preview += "..."
            
            # Format preview with proper indentation
            lines = content_preview.split('\n')
            for line in lines:
                print(f"    {line}")
            
            if i < preview_count:
                print("-" * 60)




def main():
    """Main entry point for the Email Exporter Script"""
    print("=" * 80)
    print("EMAIL EXPORTER SCRIPT")
    print("=" * 80)
    print("Starting Email Exporter Script...")
    
    script_start_time = datetime.datetime.now()
    
    try:
        # Initialize and validate configuration
        print("\n[1/6] Configuration Validation")
        print("-" * 40)
        config = EmailExporterConfig()
        config.validate_environment()
        
        # Display connection information prominently
        print(f"\n[2/6] Connection Information")
        print("-" * 40)
        print(f"Connected email address: {config.email_address}")
        print(f"Email provider: {config.provider.upper()}")
        print(f"Ready to connect to {config.provider} account: {config.email_address}")
        
        # Display IMAP settings for verification
        imap_server, port, sent_folder = config.get_imap_settings()
        print(f"IMAP Settings: {imap_server}:{port}")
        print(f"Target folder: {sent_folder}")
        
        # Test IMAP connection with retry logic
        print(f"\n[3/6] IMAP Connection")
        print("-" * 40)
        with IMAPConnectionManager(config) as imap_manager:
            # Attempt to connect
            if not imap_manager.connect():
                print("Error: Failed to establish IMAP connection after all retry attempts")
                print("Please check your credentials and internet connection.")
                sys.exit(1)
            
            # Select sent mail folder
            if not imap_manager.select_sent_folder():
                print("Error: Failed to select sent mail folder")
                print("Please verify that the sent mail folder exists for your provider.")
                sys.exit(1)
            
            print("IMAP connection and folder selection successful!")
            
            # Initialize components
            print(f"\n[4/6] Component Initialization")
            print("-" * 40)
            output_writer = OutputWriter(config.provider)
            cache_manager = CacheManager(config.provider)
            processor = EmailProcessor(imap_manager, cache_manager, output_writer)
            
            print("All components initialized successfully")
            
            # Process emails
            print(f"\n[5/6] Email Processing")
            print("-" * 40)
            print(f"Processing emails from account: {config.email_address}")
            print(f"Batch size: 500 messages")
            print(f"Progress logging interval: 100 messages")
            
            # Process emails with batch size of 500 and progress logging every 100 emails
            final_stats = processor.process_emails(batch_size=500, progress_interval=100)
            
            # Final summary and output information
            print(f"\n[6/6] Final Summary")
            print("-" * 40)
            
            # Calculate total script execution time
            script_end_time = datetime.datetime.now()
            total_duration = script_end_time - script_start_time
            total_seconds = int(total_duration.total_seconds())
            hours, remainder = divmod(total_seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            
            if hours > 0:
                duration_str = f"{hours}h {minutes}m {seconds}s"
            elif minutes > 0:
                duration_str = f"{minutes}m {seconds}s"
            else:
                duration_str = f"{seconds}s"
            
            print("Email processing completed successfully!")
            print(f"Total script execution time: {duration_str}")
            print(f"Output saved to: {output_writer.get_output_filename()}")
            print(f"Connected email address: {config.email_address}")
            
            # Show success status based on results
            if final_stats.retained > 0:
                print(f"✓ Success: {final_stats.retained} emails processed and saved")
            else:
                print("⚠ Warning: No emails were retained (check filters and content)")
            
            if final_stats.errors > 0:
                print(f"⚠ Note: {final_stats.errors} errors occurred during processing")
            
            print("\nConnection will be automatically cleaned up when exiting context manager.")
            print("=" * 80)
        
    except KeyboardInterrupt:
        print("\n" + "=" * 80)
        print("Script interrupted by user (Ctrl+C)")
        print("=" * 80)
        sys.exit(0)
    except Exception as e:
        print(f"\n" + "=" * 80)
        print(f"CRITICAL ERROR: Unexpected error occurred")
        print("-" * 40)
        print(f"Error: {e}")
        print(f"Please check your configuration and try again.")
        print("If the problem persists, check:")
        print("1. Your .env file contains valid credentials")
        print("2. Your internet connection is stable")
        print("3. Your email provider allows IMAP access")
        print("=" * 80)
        sys.exit(1)


if __name__ == "__main__":
    main()