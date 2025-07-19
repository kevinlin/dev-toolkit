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
from dataclasses import dataclass
from typing import Optional

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
            # TODO: Implement email fetching and processing
            print("Email processing not yet implemented.")
            print("Connection will be automatically cleaned up when exiting context manager.")
        
    except KeyboardInterrupt:
        print("\nScript interrupted by user")
        sys.exit(0)
    except Exception as e:
        print(f"Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()