#!/usr/bin/env python3
"""
Unit tests for IMAP timeout handling and retry logic
Tests the enhanced error handling and timeout management added in task 9
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
import imaplib
import socket
import time

# Import the classes we want to test
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from email_exporter import IMAPConnectionManager, EmailExporterConfig


class TestIMAPTimeoutHandling(unittest.TestCase):
    """Test IMAP timeout handling and retry logic"""
    
    def setUp(self):
        """Set up test fixtures"""
        # Create a mock config
        self.mock_config = Mock(spec=EmailExporterConfig)
        self.mock_config.imap_server = 'imap.test.com'
        self.mock_config.port = 993
        self.mock_config.email_address = 'test@test.com'
        self.mock_config.app_password = 'testpassword'
        self.mock_config.provider = 'test'
        self.mock_config.sent_folder = 'Sent'
        
        self.imap_manager = IMAPConnectionManager(self.mock_config)
    
    def test_connection_timeout_initialization(self):
        """Test that timeout is properly initialized"""
        self.assertEqual(self.imap_manager.fetch_timeout, 60)
        self.assertFalse(self.imap_manager.is_connected)
    
    @patch('email_exporter.imaplib.IMAP4_SSL')
    def test_connection_with_timeout_setting(self, mock_imap_class):
        """Test that socket timeout is set during connection"""
        mock_connection = Mock()
        mock_socket = Mock()
        mock_connection.sock = mock_socket
        mock_imap_class.return_value = mock_connection
        
        # Test successful connection
        result = self.imap_manager.connect()
        
        self.assertTrue(result)
        self.assertTrue(self.imap_manager.is_connected)
        mock_socket.settimeout.assert_called_once_with(60)
        mock_connection.login.assert_called_once_with('test@test.com', 'testpassword')
    
    def test_fetch_message_uids_with_timeout_retry(self):
        """Test fetch_message_uids with timeout retry logic"""
        # Setup mock connection
        mock_connection = Mock()
        self.imap_manager.connection = mock_connection
        self.imap_manager.is_connected = True
        
        # Mock first call to raise TimeoutError, second to succeed
        mock_connection.uid.side_effect = [
            TimeoutError("Connection timeout"),
            ('OK', [b'1 2 3 4 5'])
        ]
        
        with patch('builtins.print'):  # Suppress warning prints
            with patch('time.sleep'):  # Speed up test
                batches = list(self.imap_manager.fetch_message_uids(batch_size=2))
        
        # Should retry once and then succeed
        self.assertEqual(len(batches), 3)  # 5 UIDs in batches of 2: [1,2], [3,4], [5]
        self.assertEqual(mock_connection.uid.call_count, 2)
    
    def test_fetch_message_uids_max_retries_exceeded(self):
        """Test fetch_message_uids when max retries are exceeded"""
        # Setup mock connection
        mock_connection = Mock()
        self.imap_manager.connection = mock_connection
        self.imap_manager.is_connected = True
        
        # Mock all calls to raise TimeoutError
        mock_connection.uid.side_effect = TimeoutError("Connection timeout")
        
        with patch('builtins.print'):  # Suppress error prints
            with patch('time.sleep'):  # Speed up test
                batches = list(self.imap_manager.fetch_message_uids(batch_size=2))
        
        # Should fail after max retries
        self.assertEqual(len(batches), 0)
        self.assertEqual(mock_connection.uid.call_count, 2)  # 2 attempts max
    
    def test_fetch_message_with_timeout_retry(self):
        """Test fetch_message with timeout retry logic"""
        # Setup mock connection
        mock_connection = Mock()
        self.imap_manager.connection = mock_connection
        self.imap_manager.is_connected = True
        
        # Mock first call to raise TimeoutError, second to succeed
        # IMAP fetch returns: [(b'1 (RFC822 {size}', b'email content'), b')']
        mock_email_data = [(b'1 (RFC822 {1000}', b'email content'), b')']
        mock_connection.uid.side_effect = [
            OSError("Connection reset"),
            ('OK', mock_email_data)
        ]
        
        with patch('builtins.print'):  # Suppress warning prints
            with patch('time.sleep'):  # Speed up test
                with patch('email.message_from_bytes') as mock_parse:
                    mock_message = Mock()
                    mock_parse.return_value = mock_message
                    
                    result = self.imap_manager.fetch_message('123')
        
        # Should retry once and then succeed
        self.assertEqual(result, mock_message)
        self.assertEqual(mock_connection.uid.call_count, 2)
    
    def test_fetch_message_max_retries_exceeded(self):
        """Test fetch_message when max retries are exceeded"""
        # Setup mock connection
        mock_connection = Mock()
        self.imap_manager.connection = mock_connection
        self.imap_manager.is_connected = True
        
        # Mock all calls to raise TimeoutError
        mock_connection.uid.side_effect = TimeoutError("Connection timeout")
        
        with patch('builtins.print'):  # Suppress error prints
            with patch('time.sleep'):  # Speed up test
                result = self.imap_manager.fetch_message('123')
        
        # Should fail after max retries
        self.assertIsNone(result)
        self.assertEqual(mock_connection.uid.call_count, 2)  # 2 attempts max
    
    def test_fetch_message_imap_error_retry(self):
        """Test fetch_message with IMAP error retry logic"""
        # Setup mock connection
        mock_connection = Mock()
        self.imap_manager.connection = mock_connection
        self.imap_manager.is_connected = True
        
        # Mock first call to raise IMAP error, second to succeed
        # IMAP fetch returns: [(b'1 (RFC822 {size}', b'email content'), b')']
        mock_email_data = [(b'1 (RFC822 {1000}', b'email content'), b')']
        mock_connection.uid.side_effect = [
            imaplib.IMAP4.error("IMAP protocol error"),
            ('OK', mock_email_data)
        ]
        
        with patch('builtins.print'):  # Suppress warning prints
            with patch('time.sleep'):  # Speed up test
                with patch('email.message_from_bytes') as mock_parse:
                    mock_message = Mock()
                    mock_parse.return_value = mock_message
                    
                    result = self.imap_manager.fetch_message('123')
        
        # Should retry once and then succeed
        self.assertEqual(result, mock_message)
        self.assertEqual(mock_connection.uid.call_count, 2)
    
    def test_fetch_message_partial_failure_handling(self):
        """Test fetch_message handles partial failures correctly"""
        # Setup mock connection
        mock_connection = Mock()
        self.imap_manager.connection = mock_connection
        self.imap_manager.is_connected = True
        
        # Mock first call to fail with 'NO' status, second to succeed
        # IMAP fetch returns: [(b'1 (RFC822 {size}', b'email content'), b')']
        mock_email_data = [(b'1 (RFC822 {1000}', b'email content'), b')']
        mock_connection.uid.side_effect = [
            ('NO', ['Temporary failure']),
            ('OK', mock_email_data)
        ]
        
        with patch('builtins.print'):  # Suppress warning prints
            with patch('time.sleep'):  # Speed up test
                with patch('email.message_from_bytes') as mock_parse:
                    mock_message = Mock()
                    mock_parse.return_value = mock_message
                    
                    result = self.imap_manager.fetch_message('123')
        
        # Should retry once and then succeed
        self.assertEqual(result, mock_message)
        self.assertEqual(mock_connection.uid.call_count, 2)
    
    def test_search_operation_retry_on_timeout(self):
        """Test that search operations are retried on timeout"""
        # Setup mock connection
        mock_connection = Mock()
        self.imap_manager.connection = mock_connection
        self.imap_manager.is_connected = True
        
        # Mock first search to timeout, second to succeed
        mock_connection.uid.side_effect = [
            OSError("Network timeout"),
            ('OK', [b'1 2 3'])
        ]
        
        with patch('builtins.print'):  # Suppress warning prints
            with patch('time.sleep'):  # Speed up test
                batches = list(self.imap_manager.fetch_message_uids())
        
        # Should succeed after retry
        self.assertEqual(len(batches), 1)
        self.assertEqual(batches[0], ['1', '2', '3'])
        
        # Should have called uid twice (original + 1 retry)
        self.assertEqual(mock_connection.uid.call_count, 2)
    
    def test_connection_not_established_error_handling(self):
        """Test proper error handling when connection is not established"""
        # Don't set up connection (is_connected = False)
        
        with patch('builtins.print') as mock_print:
            # Test fetch_message_uids
            batches = list(self.imap_manager.fetch_message_uids())
            self.assertEqual(len(batches), 0)
            
            # Test fetch_message
            result = self.imap_manager.fetch_message('123')
            self.assertIsNone(result)
        
        # Should print appropriate error messages
        print_calls = [str(call) for call in mock_print.call_args_list]
        self.assertTrue(any('Not connected to IMAP server' in call for call in print_calls))
    
    def test_retry_delay_timing(self):
        """Test that retry delays are properly implemented"""
        # Setup mock connection
        mock_connection = Mock()
        self.imap_manager.connection = mock_connection
        self.imap_manager.is_connected = True
        
        # Mock all calls to raise timeout
        mock_connection.uid.side_effect = TimeoutError("Connection timeout")
        
        with patch('builtins.print'):  # Suppress error prints
            with patch('time.sleep') as mock_sleep:
                list(self.imap_manager.fetch_message_uids())
        
        # Should call sleep once with 2 seconds (between first and second attempt)
        mock_sleep.assert_called_once_with(2)


if __name__ == '__main__':
    unittest.main() 