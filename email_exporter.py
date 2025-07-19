#!/usr/bin/env python3
"""
Email Exporter Script

Extracts and processes sent emails from Gmail, iCloud, or Outlook accounts.
- Gmail and iCloud: Uses IMAP with app-specific passwords
- Outlook: Uses OAuth2 with Microsoft Graph API (due to Basic Auth deprecation)
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

# Import local modules
from content_processor import ContentProcessor

# Import OAuth2 module for Outlook
try:
    from outlook_oauth import create_outlook_oauth_client, OutlookMessage
    OUTLOOK_OAUTH_AVAILABLE = True
except ImportError:
    OUTLOOK_OAUTH_AVAILABLE = False
    def create_outlook_oauth_client(*args, **kwargs):
        raise ImportError("OAuth2 dependencies not available. Run: uv pip install msal requests")

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
        'icloud': ProviderConfig('imap.mail.me.com', 993, '"Sent Messages"'),
        'outlook': ProviderConfig('outlook.office365.com', 993, 'Sent Items')
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
        For Outlook, APP_PASSWORD is optional (OAuth2 is used instead).
        Exits with error message if any required fields are missing.
        """
        # Load environment variables from .env file if dotenv is available
        if DOTENV_AVAILABLE:
            load_dotenv()
        else:
            print("Warning: python-dotenv not installed. Reading environment variables directly.")
        
        # Required environment variables (basic)
        required_vars = ['PROVIDER', 'EMAIL_ADDRESS']
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
        self.app_password = os.getenv('APP_PASSWORD', '').strip()
        
        # Validate provider
        if self.provider not in self.PROVIDER_CONFIGS:
            print(f"Error: Invalid PROVIDER '{self.provider}'. Supported providers: {', '.join(self.PROVIDER_CONFIGS.keys())}")
            sys.exit(1)
        
        # Check APP_PASSWORD requirement based on provider
        if self.provider in ['gmail', 'icloud']:
            # Traditional providers require app password
            if not self.app_password:
                print(f"Error: APP_PASSWORD is required for {self.provider}")
                print("Please set APP_PASSWORD in your .env file")
                sys.exit(1)
        elif self.provider == 'outlook':
            # Outlook uses OAuth2, app password is optional/ignored
            if self.app_password:
                print("ℹ️  Note: APP_PASSWORD is ignored for Outlook (using OAuth2 instead)")
            print("🔐 Outlook will use OAuth2 authentication (Microsoft Graph API)")
        
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
            
            # For Outlook, try common alternative folder names
            if self.config.provider == 'outlook':
                alternative_folders = ['Sent', 'Sent Messages', 'INBOX.Sent Items', 'INBOX/Sent Items', 'INBOX.Sent', 'INBOX/Sent']
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


class CacheManager:
    """Manages UID caching and content hash tracking for duplicate prevention"""
    
    def __init__(self, provider: str, output_dir: str = "output"):
        """
        Initialize cache manager for the specified provider.
        
        Args:
            provider: Email provider ('gmail', 'icloud', or 'outlook')
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
            provider: Email provider ('gmail', 'icloud', or 'outlook')
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


class OutlookOAuth2Processor:
    """Handles Outlook email processing using OAuth2 and Microsoft Graph API"""
    
    def __init__(self, outlook_client, cache_manager: Optional[CacheManager] = None, output_writer: Optional[OutputWriter] = None):
        self.outlook_client = outlook_client
        self.stats = ProcessingStats()
        self.processed_messages = []  # Store processed messages for preview/summary
        self.content_processor = ContentProcessor()  # Initialize content processor
        self.cache_manager = cache_manager  # Cache manager for duplicate prevention
        self.output_writer = output_writer  # Output writer for file management
    
    def process_emails(self, batch_size: int = 500, progress_interval: int = 100) -> ProcessingStats:
        """
        Process Outlook emails using Microsoft Graph API
        
        Args:
            batch_size: Number of messages to fetch per batch (Graph API handles pagination)
            progress_interval: Log progress every N processed emails
            
        Returns:
            ProcessingStats: Final processing statistics
        """
        print("Starting Outlook email processing using OAuth2...")
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
            # Get sent messages from Graph API
            print(f"Fetching sent messages from Microsoft Graph API...")
            messages = self.outlook_client.get_sent_messages(limit=batch_size)
            
            if not messages:
                print("No messages found in sent folder")
                self.stats.end_processing()
                return self.stats
            
            print(f"Found {len(messages)} messages in sent folder")
            
            # Process messages
            for i, message in enumerate(messages, 1):
                try:
                    # Check if message is already processed using cache
                    if self.cache_manager and self.cache_manager.is_processed(message.id):
                        self.stats.skipped_duplicate += 1
                        continue
                    
                    # Process the message
                    was_retained = self._process_outlook_message(message)
                    
                    # Only mark message as processed in cache if it was actually retained
                    if self.cache_manager and was_retained:
                        self.cache_manager.mark_processed(message.id)
                    
                    # Update total count
                    self.stats.total_fetched += 1
                    
                    # Enhanced progress logging at specified intervals
                    if self.stats.total_fetched % progress_interval == 0:
                        print(f"Progress: {self.stats.get_quick_stats()}")
                        
                except Exception as e:
                    print(f"Warning: Error processing message {message.id}: {str(e)}")
                    self.stats.increment_error_type('processing')
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
            print("\nOutlook email processing completed!")
            print(self.stats.get_summary())
            
            # Show preview of first 3 retained messages
            self._show_message_preview()
            
            return self.stats
            
        except Exception as e:
            print(f"Error: Critical failure during Outlook email processing: {str(e)}")
            self.stats.increment_error_type('processing')
            self.stats.end_processing()
            return self.stats
    
    def _process_outlook_message(self, message: OutlookMessage) -> bool:
        """
        Process a single Outlook message from Graph API
        
        Args:
            message: OutlookMessage from Graph API
            
        Returns:
            bool: True if message was retained, False if filtered out
        """
        try:
            # Extract body content
            body_content = message.body_content
            
            # Additional content processing (HTML to text, etc.)
            if body_content:
                # For Outlook OAuth2, HTML to text conversion is already done by Graph API processing
                # Just do basic cleanup without aggressive whitespace normalization
                
                # Strip quoted replies
                body_content = self.content_processor.strip_quoted_replies(body_content)
                
                # Do minimal whitespace cleanup (preserve paragraph structure)
                body_content = self._normalize_outlook_content(body_content)
            
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
            
            # Store processed message with cleaned content for preview
            self.stats.retained += 1
            self.processed_messages.append({
                'uid': message.id,
                'subject': message.subject,
                'date': message.received_datetime,
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
            print(f"Error: Failed to process Outlook message {message.id}: {str(e)}")
            self.stats.increment_error_type('processing')
            return False  # Message was not retained due to error
    
    def _normalize_outlook_content(self, content: str) -> str:
        """
        Normalize Outlook content while preserving paragraph structure.
        Less aggressive than the standard normalize_whitespace function.
        
        Args:
            content: Content to normalize
            
        Returns:
            str: Content with normalized whitespace but preserved paragraphs
        """
        if not content:
            return ""
        
        try:
            # Replace different types of line breaks with standard \n
            content = re.sub(r'\r\n|\r', '\n', content)
            
            # Remove excessive whitespace within lines
            content = re.sub(r'[ \t]+', ' ', content)
            
            # Remove leading/trailing whitespace from each line
            lines = content.split('\n')
            cleaned_lines = [line.strip() for line in lines]
            
            # Remove excessive blank lines (more than 2 consecutive) but preserve paragraph structure
            result_lines = []
            blank_count = 0
            
            for line in cleaned_lines:
                if line:  # Non-blank line
                    result_lines.append(line)
                    blank_count = 0
                else:  # Blank line
                    blank_count += 1
                    # Allow up to 1 blank line for paragraph separation
                    if blank_count <= 1:
                        result_lines.append(line)
            
            # Remove trailing blank lines
            while result_lines and not result_lines[-1]:
                result_lines.pop()
            
            # Join lines back together
            content = '\n'.join(result_lines)
            
            return content
            
        except Exception as e:
            print(f"Warning: Error normalizing Outlook content: {str(e)}")
            return content.strip() if content else ""
    
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
            print(f"  ID: {message['uid']}")
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
        
        # Check if this is Outlook and handle OAuth2 vs IMAP
        if config.provider == 'outlook':
            print("🔐 Outlook detected - Using OAuth2 authentication (Microsoft Graph API)")
            print("⚠️  Note: App passwords are deprecated for Outlook.com accounts")
            
            # Check OAuth2 dependencies
            if not OUTLOOK_OAUTH_AVAILABLE:
                print("❌ Error: OAuth2 dependencies not available")
                print("Please install required packages:")
                print("  uv pip install msal requests")
                sys.exit(1)
            
            # OAuth2 Authentication for Outlook
            print(f"\n[3/6] OAuth2 Authentication")
            print("-" * 40)
            
            try:
                outlook_client = create_outlook_oauth_client(config.email_address)
                
                print("🔑 Starting OAuth2 authentication...")
                if not outlook_client.acquire_token_interactive():
                    print("❌ OAuth2 authentication failed")
                    print("Please ensure you have a valid Microsoft account and internet connection")
                    sys.exit(1)
                
                # Test connection
                if not outlook_client.test_connection():
                    print("❌ Failed to connect to Microsoft Graph API")
                    sys.exit(1)
                
                print("✅ OAuth2 authentication successful!")
                
                # Initialize components for Outlook
                print(f"\n[4/6] Component Initialization")
                print("-" * 40)
                output_writer = OutputWriter(config.provider)
                cache_manager = CacheManager(config.provider)
                processor = OutlookOAuth2Processor(outlook_client, cache_manager, output_writer)
                
                print("All components initialized successfully for Outlook OAuth2")
                
                # Process emails using Graph API
                print(f"\n[5/6] Email Processing (Microsoft Graph API)")
                print("-" * 40)
                print(f"Processing emails from account: {config.email_address}")
                print(f"Using Microsoft Graph API for Outlook")
                print(f"Progress logging interval: 100 messages")
                
                # Process emails using OAuth2/Graph API
                final_stats = processor.process_emails(batch_size=500, progress_interval=100)
                
            except Exception as e:
                print(f"❌ OAuth2 processing error: {str(e)}")
                sys.exit(1)
                
        else:
            # Traditional IMAP for Gmail and iCloud
            print(f"📧 Using IMAP authentication for {config.provider}")
            
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
                print(f"\n[5/6] Email Processing (IMAP)")
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
        
        if config.provider == 'outlook':
            print(f"✅ Used OAuth2 authentication for Outlook")
        else:
            print(f"✅ Used IMAP authentication for {config.provider}")
        
        print(f"Output saved to: {output_writer.get_output_filename()}")
        print(f"Connected email address: {config.email_address}")
        
        # Show success status based on results
        if final_stats.retained > 0:
            print(f"✓ Success: {final_stats.retained} emails processed and saved")
        else:
            print("⚠ Warning: No emails were retained (check filters and content)")
        
        if final_stats.errors > 0:
            print(f"⚠ Note: {final_stats.errors} errors occurred during processing")
        
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