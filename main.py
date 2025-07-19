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


class EmailProcessor:
    """Handles email fetching, processing, and statistics tracking"""
    
    def __init__(self, imap_manager: IMAPConnectionManager):
        self.imap_manager = imap_manager
        self.stats = ProcessingStats()
        self.processed_messages = []  # Store processed messages for now
    
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
        Process a single email message.
        
        Args:
            uid: Message UID
            message: Parsed email message
        """
        try:
            # For now, just extract basic information and count as retained
            # This will be expanded in later tasks with content filtering
            
            # Get basic message info
            subject = message.get('Subject', 'No Subject')
            date = message.get('Date', 'No Date')
            
            # Simple validation - check if message has content
            if self._has_valid_content(message):
                self.stats.retained += 1
                # Store basic info for now (will be replaced with actual content processing)
                self.processed_messages.append({
                    'uid': uid,
                    'subject': subject,
                    'date': date
                })
            else:
                self.stats.skipped_short += 1
                
        except Exception as e:
            print(f"Error processing message content for UID {uid}: {str(e)}")
            self.stats.errors += 1
    
    def _has_valid_content(self, message: email.message.Message) -> bool:
        """
        Basic validation to check if message has content.
        This is a placeholder that will be expanded in later tasks.
        
        Args:
            message: Email message to validate
            
        Returns:
            bool: True if message appears to have valid content
        """
        try:
            # Basic check - ensure message has a subject or body
            subject = message.get('Subject', '')
            
            # Try to get some body content
            body = ""
            if message.is_multipart():
                for part in message.walk():
                    if part.get_content_type() == "text/plain":
                        body = part.get_payload(decode=True)
                        if isinstance(body, bytes):
                            body = body.decode('utf-8', errors='ignore')
                        break
            else:
                body = message.get_payload(decode=True)
                if isinstance(body, bytes):
                    body = body.decode('utf-8', errors='ignore')
            
            # Simple validation - has subject or body content
            return bool(subject.strip()) or bool(body.strip())
            
        except Exception:
            # If we can't parse the message, consider it invalid
            return False


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