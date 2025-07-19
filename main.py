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
from dataclasses import dataclass
from typing import Optional, Iterator, List

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
    """Statistics for email processing"""
    total_fetched: int = 0
    skipped_short: int = 0
    skipped_duplicate: int = 0
    skipped_system: int = 0
    retained: int = 0
    errors: int = 0
    
    def get_summary(self) -> str:
        """Get a formatted summary of processing statistics"""
        return (f"Processing Summary:\n"
                f"  Total fetched: {self.total_fetched}\n"
                f"  Skipped (short): {self.skipped_short}\n"
                f"  Skipped (duplicate): {self.skipped_duplicate}\n"
                f"  Skipped (system): {self.skipped_system}\n"
                f"  Retained: {self.retained}\n"
                f"  Errors: {self.errors}")


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
    
    def connect(self) -> bool:
        """
        Establish IMAP connection with retry logic and exponential backoff.
        
        Returns:
            bool: True if connection successful, False otherwise
        """
        for attempt in range(self.max_retries):
            try:
                print(f"Attempting IMAP connection to {self.config.imap_server}:{self.config.port} (attempt {attempt + 1}/{self.max_retries})")
                
                # Create SSL IMAP connection
                self.connection = imaplib.IMAP4_SSL(self.config.imap_server, self.config.port)
                
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
                
        except Exception as e:
            print(f"Error fetching message UIDs: {str(e)}")
            return
    
    def fetch_message(self, uid: str) -> Optional[email.message.Message]:
        """
        Fetch a single email message by UID.
        
        Args:
            uid: Message UID to fetch
            
        Returns:
            email.message.Message: Parsed email message or None if error
        """
        if not self.is_connected or not self.connection:
            print("Error: Not connected to IMAP server")
            return None
        
        try:
            # Fetch message by UID
            status, data = self.connection.uid('fetch', uid, '(RFC822)')
            
            if status != 'OK':
                print(f"Warning: Failed to fetch message UID {uid}: {data}")
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
            
        except Exception as e:
            print(f"Error fetching message UID {uid}: {str(e)}")
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
    
    def normalize_whitespace(self, content: str) -> str:
        """
        Normalize whitespace and standardize line breaks.
        
        Args:
            content: Content to normalize
            
        Returns:
            str: Content with normalized whitespace
        """
        if not content:
            return ""
        
        try:
            # Replace different types of line breaks with standard \n
            content = re.sub(r'\r\n|\r', '\n', content)
            
            # Remove excessive whitespace while preserving paragraph structure
            # Replace multiple spaces with single space
            content = re.sub(r'[ \t]+', ' ', content)
            
            # Replace multiple consecutive newlines with maximum of 2 (to preserve paragraphs)
            content = re.sub(r'\n\s*\n\s*\n+', '\n\n', content)
            
            # Remove leading/trailing whitespace from each line
            lines = content.split('\n')
            cleaned_lines = [line.strip() for line in lines]
            
            # Remove empty lines at the beginning and end
            while cleaned_lines and not cleaned_lines[0]:
                cleaned_lines.pop(0)
            while cleaned_lines and not cleaned_lines[-1]:
                cleaned_lines.pop()
            
            # Join lines back together
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


class EmailProcessor:
    """Handles email fetching, processing, and statistics tracking"""
    
    def __init__(self, imap_manager: IMAPConnectionManager):
        self.imap_manager = imap_manager
        self.stats = ProcessingStats()
        self.processed_messages = []  # Store processed messages for now
        self.content_processor = ContentProcessor()  # Initialize content processor
    
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
        
        try:
            # Process emails in batches
            for batch_uids in self.imap_manager.fetch_message_uids(batch_size):
                self._process_batch(batch_uids, progress_interval)
            
            # Final summary
            print("\nEmail processing completed!")
            print(self.stats.get_summary())
            
            return self.stats
            
        except Exception as e:
            print(f"Error during email processing: {str(e)}")
            self.stats.errors += 1
            return self.stats
    
    def _process_batch(self, uids: List[str], progress_interval: int) -> None:
        """
        Process a batch of message UIDs sequentially.
        
        Args:
            uids: List of message UIDs to process
            progress_interval: Log progress every N processed emails
        """
        for uid in uids:
            try:
                # Fetch individual message
                message = self.imap_manager.fetch_message(uid)
                
                if message is None:
                    self.stats.errors += 1
                    continue
                
                # Process the message
                self._process_single_message(uid, message)
                
                # Update total count
                self.stats.total_fetched += 1
                
                # Log progress at specified intervals
                if self.stats.total_fetched % progress_interval == 0:
                    print(f"Progress: Processed {self.stats.total_fetched} emails "
                          f"(retained: {self.stats.retained}, errors: {self.stats.errors})")
                
            except Exception as e:
                print(f"Error processing message UID {uid}: {str(e)}")
                self.stats.errors += 1
                continue
    
    def _process_single_message(self, uid: str, message: email.message.Message) -> None:
        """
        Process a single email message with content extraction and filtering.
        
        Args:
            uid: Message UID
            message: Parsed email message
        """
        try:
            # Check if message is system-generated first
            if self.content_processor.is_system_generated(message):
                self.stats.skipped_system += 1
                return
            
            # Extract and clean body content
            body_content = self.content_processor.extract_body_content(message)
            
            # Validate content quality
            if not self.content_processor.is_valid_content(body_content):
                self.stats.skipped_short += 1
                return
            
            # Get basic message info
            subject = message.get('Subject', 'No Subject')
            date = message.get('Date', 'No Date')
            
            # Store processed message with cleaned content
            self.stats.retained += 1
            self.processed_messages.append({
                'uid': uid,
                'subject': subject,
                'date': date,
                'content': body_content,
                'word_count': len(body_content.split())
            })
                
        except Exception as e:
            print(f"Error processing message content for UID {uid}: {str(e)}")
            self.stats.errors += 1
    



def main():
    """Main entry point for the Email Exporter Script"""
    print("Email Exporter Script Starting...")
    
    try:
        # Initialize and validate configuration
        config = EmailExporterConfig()
        config.validate_environment()
        
        # Display connection information
        print(f"Ready to connect to {config.provider} account: {config.email_address}")
        
        # Display IMAP settings for verification
        imap_server, port, sent_folder = config.get_imap_settings()
        print(f"IMAP Settings: {imap_server}:{port}, Sent folder: {sent_folder}")
        
        # Test IMAP connection with retry logic
        with IMAPConnectionManager(config) as imap_manager:
            # Attempt to connect
            if not imap_manager.connect():
                print("Error: Failed to establish IMAP connection after all retry attempts")
                sys.exit(1)
            
            # Select sent mail folder
            if not imap_manager.select_sent_folder():
                print("Error: Failed to select sent mail folder")
                sys.exit(1)
            
            print("IMAP connection and folder selection successful!")
            
            # Initialize email processor and start processing
            processor = EmailProcessor(imap_manager)
            
            # Process emails with batch size of 500 and progress logging every 100 emails
            final_stats = processor.process_emails(batch_size=500, progress_interval=100)
            
            print("\nEmail processing completed successfully!")
            print("Connection will be automatically cleaned up when exiting context manager.")
        
    except KeyboardInterrupt:
        print("\nScript interrupted by user")
        sys.exit(0)
    except Exception as e:
        print(f"Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()