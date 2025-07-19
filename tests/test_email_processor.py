#!/usr/bin/env python3
"""
Unit tests for EmailProcessor class changes
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
        """Test processing handles messages with missing headers"""
        # Create test message without subject/date
        msg = email.message.EmailMessage()
        msg['From'] = 'user@example.com'
        msg.set_content("Valid content for processing")
        
        extracted_content = "Valid content for processing with cleaning applied"
        
        # Mock content processor methods
        with patch.object(self.processor.content_processor, 'is_system_generated', return_value=False):
            with patch.object(self.processor.content_processor, 'extract_body_content', return_value=extracted_content):
                with patch.object(self.processor.content_processor, 'is_valid_content', return_value=True):
                    self.processor._process_single_message('456', msg)
                    
                    # Should still process the message
                    self.assertEqual(self.processor.stats.retained, 1)
                    
                    # Should use default values for missing headers
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
        """Test that _process_batch calls _process_single_message for each UID"""
        uids = ['123', '456', '789']
        
        # Mock fetch_message to return test messages
        test_messages = []
        for i, uid in enumerate(uids):
            msg = email.message.EmailMessage()
            msg['Subject'] = f'Test Email {i}'
            msg['From'] = 'user@example.com'
            msg.set_content(f"Test content {i}")
            test_messages.append(msg)
        
        self.mock_imap_manager.fetch_message.side_effect = test_messages
        
        # Mock _process_single_message to track calls
        with patch.object(self.processor, '_process_single_message') as mock_process:
            self.processor._process_batch(uids, 100)
            
            # Should call _process_single_message for each UID
            self.assertEqual(mock_process.call_count, 3)
            
            # Verify calls with correct UIDs and messages
            for i, (call_args, _) in enumerate(mock_process.call_args_list):
                self.assertEqual(call_args[0], uids[i])  # UID
                self.assertEqual(call_args[1], test_messages[i])  # Message
    
    def test_process_batch_handles_fetch_errors(self):
        """Test that _process_batch handles fetch errors gracefully"""
        uids = ['123', '456', '789']
        
        # Mock fetch_message to return None for some messages
        self.mock_imap_manager.fetch_message.side_effect = [None, MagicMock(), None]
        
        with patch.object(self.processor, '_process_single_message') as mock_process:
            self.processor._process_batch(uids, 100)
            
            # Should only call _process_single_message for successful fetches
            self.assertEqual(mock_process.call_count, 1)
            
            # Should increment error counter for failed fetches
            self.assertEqual(self.processor.stats.errors, 2)
    
    def test_process_batch_handles_processing_exceptions(self):
        """Test that _process_batch handles processing exceptions gracefully"""
        uids = ['123', '456']
        
        # Mock fetch_message to return test messages
        test_messages = [MagicMock(), MagicMock()]
        self.mock_imap_manager.fetch_message.side_effect = test_messages
        
        # Mock _process_single_message to raise exception for first message
        with patch('builtins.print'):  # Suppress error print
            with patch.object(self.processor, '_process_single_message', side_effect=[Exception("Process error"), None]):
                self.processor._process_batch(uids, 100)
                
                # Should increment error counter for exception
                self.assertEqual(self.processor.stats.errors, 1)
                
                # Only the successful message should increment total_fetched
                self.assertEqual(self.processor.stats.total_fetched, 1)
    
    def test_process_batch_progress_logging(self):
        """Test that _process_batch logs progress at specified intervals"""
        uids = ['123', '456', '789', '101', '102']
        progress_interval = 2
        
        # Mock fetch_message to return test messages
        test_messages = [MagicMock() for _ in uids]
        self.mock_imap_manager.fetch_message.side_effect = test_messages
        
        # Mock _process_single_message
        with patch.object(self.processor, '_process_single_message'):
            with patch('builtins.print') as mock_print:
                self.processor._process_batch(uids, progress_interval)
                
                # Should log progress at intervals (messages 2 and 4)
                progress_calls = [call for call in mock_print.call_args_list 
                                if 'Progress:' in str(call)]
                self.assertEqual(len(progress_calls), 2)  # At messages 2 and 4
    
    def test_process_emails_integration(self):
        """Test process_emails method integration"""
        # Mock fetch_message_uids to return batches
        batch1 = ['123', '456']
        batch2 = ['789', '101']
        self.mock_imap_manager.fetch_message_uids.return_value = [batch1, batch2]
        
        # Mock _process_batch
        with patch.object(self.processor, '_process_batch') as mock_process_batch:
            with patch('builtins.print'):  # Suppress output
                result = self.processor.process_emails(batch_size=500, progress_interval=100)
                
                # Should call _process_batch for each batch
                self.assertEqual(mock_process_batch.call_count, 2)
                
                # Verify batch calls
                call_args_list = mock_process_batch.call_args_list
                self.assertEqual(call_args_list[0][0][0], batch1)  # First batch
                self.assertEqual(call_args_list[1][0][0], batch2)  # Second batch
                
                # Should return stats
                self.assertIsInstance(result, ProcessingStats)
    
    def test_process_emails_exception_handling(self):
        """Test process_emails handles exceptions gracefully"""
        # Mock fetch_message_uids to raise exception
        self.mock_imap_manager.fetch_message_uids.side_effect = Exception("Fetch error")
        
        with patch('builtins.print'):  # Suppress error print
            result = self.processor.process_emails()
            
            # Should increment error counter and return stats
            self.assertEqual(result.errors, 1)
            self.assertIsInstance(result, ProcessingStats)


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