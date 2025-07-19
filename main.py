#!/usr/bin/env python3
"""
Email Exporter Script

Extracts and processes sent emails from Gmail or iCloud accounts via IMAP.
Processes only sent messages, extracts clean body content while excluding 
quoted replies and duplicates, and outputs content to timestamped plain text files.
"""

import os
import sys
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
        'icloud': ProviderConfig('imap.mail.me.com', 993, 'Sent Messages')
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
        
        # TODO: Implement IMAP connection and email processing
        print("Configuration setup complete. Email processing not yet implemented.")
        
    except KeyboardInterrupt:
        print("\nScript interrupted by user")
        sys.exit(0)
    except Exception as e:
        print(f"Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()