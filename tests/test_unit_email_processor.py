#!/usr/bin/env python3
"""
Unit tests for EmailProcessor class
"""

import unittest
import email
from unittest.mock import patch, MagicMock
import sys
import os

# Add the parent directory to the path so we can import main
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import EmailProcessor, ProcessingStats, ContentProcessor


class TestEmailProcessor(unittest.TestCase):
    """Test cases for EmailProcessor class"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.mock_imap_manager = MagicMock()
        self.processor = EmailProcessor(self.mock_imap_manager)
    
    def test_init_creates_content_processor(self):
        """Test that EmailProcessor initializes ContentProcessor"""
        self.assertIsInstance(self.processor.content_processor, ContentProcessor)
        self.assertIsInstance(self.processor.stats, ProcessingStats)
        self.assertEqual(self.processor.processed_messages, [])
    
    def test_process_single_message_system_generated(self):
        """Test processing skips system-generated messages"""
        # Create test message
        msg = email.message.EmailMessage()
        msg['Subject'] = 'Auto-Reply: Out of Office'
        msg['From'] = 'user@example.com'
        msg.set_content("I'm out of office")
        
        # Mock content processor to return True for system-generated
        with patch.object(self.processor.content_processor, 'is_system_generated', return_value=True):
            self.processor._process_single_message('123', msg)
            
            # Should increment skipped_system counter
            self.assertEqual(self.processor.stats.skipped_system, 1)
            self.assertEqual(self.processor.stats.retained, 0)
            self.assertEqual(len(self.processor.processed_messages), 0)
    
    def test_process_single_message_invalid_content(self):
        """Test processing skips messages with invalid content"""
        # Create test message
        msg = email.message.EmailMessage()
        msg['Subject'] = 'Test Email'
        msg['From'] = 'user@example.com'
        msg.set_content("Short")
        
        # Mock content processor methods
        with patch.object(self.processor.content_processor, 'is_system_generated', return_value=False):
            with patch.object(self.processor.content_processor, 'extract_body_content', return_value="Short content"):
                with patch.object(self.processor.content_processor, 'is_valid_content', return_value=False):
                    self.processor._process_single_message('123', msg)
                    
                    # Should increment skipped_short counter
                    self.assertEqual(self.processor.stats.skipped_short, 1)
                    self.assertEqual(self.processor.stats.retained, 0)
                    self.assertEqual(len(self.processor.processed_messages), 0)
    
    def test_process_single_message_valid_content(self):
        """Test processing retains messages with valid content"""
        # Create test message
        msg = email.message.EmailMessage()
        msg['Subject'] = 'Important Email'
        msg['From'] = 'user@example.com'
        msg['Date'] = 'Mon, 15 Jan 2024 10:30:00 +0000'
        msg.set_content("This is a valid email with sufficient content for processing")
        
        extracted_content = "This is a valid email with sufficient content for processing and cleaning applied"
        
        # Mock content processor methods
        with patch.object(self.processor.content_processor, 'is_system_generated', return_value=False):
            with patch.object(self.processor.content_processor, 'extract_body_content', return_value=extracted_content):
                with patch.object(self.processor.content_processor, 'is_valid_content', return_value=True):
                    self.processor._process_single_message('123', msg)
                    
                    # Should increment retained counter
                    self.assertEqual(self.processor.stats.retained, 1)
                    self.assertEqual(self.processor.stats.skipped_short, 0)
                    self.assertEqual(self.processor.stats.skipped_system, 0)
                    
                    # Should store processed message
                    self.assertEqual(len(self.processor.processed_messages), 1)
                    processed_msg = self.processor.processed_messages[0]
                    
                    self.assertEqual(processed_msg['uid'], '123')
                    self.assertEqual(processed_msg['subject'], 'Important Email')
                    self.assertEqual(processed_msg['date'], 'Mon, 15 Jan 2024 10:30:00 +0000')
                    self.assertEqual(processed_msg['content'], extracted_content)
                    self.assertEqual(processed_msg['word_count'], len(extracted_content.split()))
    
    def test_process_single_message_missing_headers(self):
        """Test processing handles messages with missing headers gracefully"""
        # Create test message without standard headers
        msg = email.message.EmailMessage()
        # No Subject or Date headers
        msg['From'] = 'user@example.com'
        msg.set_content("This is a valid email with sufficient content for processing purposes and validation requirements")
        
        extracted_content = "This is a valid email with sufficient content for processing purposes and validation requirements"
        
        # Mock content processor methods
        with patch.object(self.processor.content_processor, 'is_system_generated', return_value=False):
            with patch.object(self.processor.content_processor, 'extract_body_content', return_value=extracted_content):
                with patch.object(self.processor.content_processor, 'is_valid_content', return_value=True):
                    self.processor._process_single_message('456', msg)
                    
                    # Should still process successfully with default values
                    self.assertEqual(self.processor.stats.retained, 1)
                    self.assertEqual(len(self.processor.processed_messages), 1)
                    
                    processed_msg = self.processor.processed_messages[0]
                    self.assertEqual(processed_msg['subject'], 'No Subject')
                    self.assertEqual(processed_msg['date'], 'No Date')
    
    def test_process_single_message_exception_handling(self):
        """Test processing handles exceptions gracefully"""
        # Create test message
        msg = email.message.EmailMessage()
        msg['Subject'] = 'Test Email'
        msg['From'] = 'user@example.com'
        msg.set_content("Test content")
        
        # Mock content processor to raise exception
        with patch('builtins.print'):  # Suppress error print
            with patch.object(self.processor.content_processor, 'is_system_generated', side_effect=Exception("Test error")):
                self.processor._process_single_message('789', msg)
                
                # Should increment error counter
                self.assertEqual(self.processor.stats.errors, 1)
                self.assertEqual(self.processor.stats.retained, 0)
                self.assertEqual(len(self.processor.processed_messages), 0)
    
    def test_process_batch_calls_process_single_message(self):
        """Test that process_batch calls _process_single_message for each UID"""
        uids = ['uid1', 'uid2', 'uid3']
        
        # Mock fetch_message to return a message for each UID
        mock_msg = email.message.EmailMessage()
        mock_msg['Subject'] = 'Test'
        mock_msg.set_content("Test content")
        self.mock_imap_manager.fetch_message.return_value = mock_msg
        
        # Mock _process_single_message to avoid actual processing
        with patch.object(self.processor, '_process_single_message') as mock_process:
            self.processor._process_batch(uids, 100)
            
            # Should call _process_single_message once for each UID
            self.assertEqual(mock_process.call_count, 3)
            
            # Should call fetch_message once for each UID
            self.assertEqual(self.mock_imap_manager.fetch_message.call_count, 3)
    
    def test_process_batch_handles_fetch_errors(self):
        """Test that process_batch handles fetch errors gracefully"""
        uids = ['uid1', 'uid2']
        
        # Mock fetch_message to raise exception
        self.mock_imap_manager.fetch_message.side_effect = Exception("Fetch error")
        
        with patch('builtins.print'):  # Suppress error prints
            self.processor._process_batch(uids, 100)
            
            # Should increment error counter for each failed fetch
            self.assertEqual(self.processor.stats.errors, 2)
    
    def test_process_batch_handles_processing_exceptions(self):
        """Test that process_batch handles processing exceptions gracefully"""
        uids = ['uid1']
        
        # Mock fetch_message to return a message
        mock_msg = email.message.EmailMessage()
        self.mock_imap_manager.fetch_message.return_value = mock_msg
        
        # Mock _process_single_message to raise exception
        with patch('builtins.print'):  # Suppress error prints
            with patch.object(self.processor, '_process_single_message', side_effect=Exception("Process error")):
                self.processor._process_batch(uids, 100)
                
                # Error should be handled within _process_single_message
                # This test ensures the batch processing doesn't crash
                pass
    
    def test_process_batch_progress_logging(self):
        """Test that process_batch logs progress correctly"""
        uids = ['uid1', 'uid2', 'uid3']
        
        # Mock fetch_message to return a message
        mock_msg = email.message.EmailMessage()
        self.mock_imap_manager.fetch_message.return_value = mock_msg
        
        # Mock _process_single_message to avoid actual processing
        with patch.object(self.processor, '_process_single_message'):
            with patch('builtins.print') as mock_print:
                self.processor._process_batch(uids, 2)  # Progress every 2 messages
                
                # Should print progress at message 2
                mock_print.assert_called()
    
    def test_process_emails_exception_handling(self):
        """Test that process_emails handles top-level exceptions gracefully"""
        # Mock fetch_message_uids to raise exception
        self.mock_imap_manager.fetch_message_uids.side_effect = Exception("IMAP error")
        
        with patch('builtins.print'):  # Suppress error prints
            stats = self.processor.process_emails()
            
            # Should return stats even on error
            self.assertIsInstance(stats, ProcessingStats)


class TestProcessingStats(unittest.TestCase):
    """Test cases for ProcessingStats class"""
    
    def test_init_default_values(self):
        """Test ProcessingStats initialization with default values"""
        stats = ProcessingStats()
        
        self.assertEqual(stats.total_fetched, 0)
        self.assertEqual(stats.skipped_short, 0)
        self.assertEqual(stats.skipped_duplicate, 0)
        self.assertEqual(stats.skipped_system, 0)
        self.assertEqual(stats.retained, 0)
        self.assertEqual(stats.errors, 0)
    
    def test_init_custom_values(self):
        """Test ProcessingStats initialization with custom values"""
        stats = ProcessingStats(
            total_fetched=100,
            skipped_short=10,
            skipped_duplicate=5,
            skipped_system=15,
            retained=65,
            errors=5
        )
        
        self.assertEqual(stats.total_fetched, 100)
        self.assertEqual(stats.skipped_short, 10)
        self.assertEqual(stats.skipped_duplicate, 5)
        self.assertEqual(stats.skipped_system, 15)
        self.assertEqual(stats.retained, 65)
        self.assertEqual(stats.errors, 5)
    
    def test_get_summary(self):
        """Test ProcessingStats summary generation"""
        stats = ProcessingStats(
            total_fetched=100,
            skipped_short=10,
            skipped_duplicate=5,
            skipped_system=15,
            retained=65,
            errors=5
        )
        
        summary = stats.get_summary()
        
        # Check that all values are included in summary
        self.assertIn("Total fetched: 100", summary)
        self.assertIn("Skipped (short): 10", summary)
        self.assertIn("Skipped (duplicate): 5", summary)
        self.assertIn("Skipped (system): 15", summary)
        self.assertIn("Retained: 65", summary)
        self.assertIn("Errors: 5", summary)
        self.assertIn("Processing Summary:", summary)


if __name__ == '__main__':
    unittest.main() 