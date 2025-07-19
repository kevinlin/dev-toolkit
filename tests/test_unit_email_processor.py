#!/usr/bin/env python3
"""
Unit tests for EmailProcessor class
"""

import unittest
import email
from unittest.mock import patch, MagicMock, Mock
import sys
import os

# Add the parent directory to the path so we can import main
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import EmailProcessor, ProcessingStats, ContentProcessor


class TestEmailProcessor(unittest.TestCase):
    """Test cases for EmailProcessor class"""
    
    def setUp(self):
        """Set up test fixtures"""
        # Create mock IMAP manager
        self.mock_imap_manager = Mock()
        
        # Create mock cache manager
        self.mock_cache_manager = Mock()
        self.mock_cache_manager.is_processed.return_value = False  # Default: not processed
        self.mock_cache_manager.get_content_hashes.return_value = set()  # Default: no cached hashes
        
        # Create mock output writer  
        self.mock_output_writer = Mock()
        
        # Create EmailProcessor with mocked dependencies
        self.processor = EmailProcessor(
            self.mock_imap_manager, 
            self.mock_cache_manager, 
            self.mock_output_writer
        )
    
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

    # New comprehensive tests for task 9 requirements
    
    def test_enhanced_error_categorization(self):
        """Test that enhanced error categorization works correctly"""
        stats = ProcessingStats()
        
        # Test each error type
        stats.increment_error_type('fetch')
        self.assertEqual(stats.fetch_errors, 1)
        self.assertEqual(stats.errors, 1)
        
        stats.increment_error_type('timeout')
        self.assertEqual(stats.timeout_errors, 1)
        self.assertEqual(stats.errors, 2)
        
        stats.increment_error_type('processing')
        self.assertEqual(stats.processing_errors, 1)
        self.assertEqual(stats.errors, 3)
        
        stats.increment_error_type('cache')
        self.assertEqual(stats.cache_errors, 1)
        self.assertEqual(stats.errors, 4)
        
        stats.increment_error_type('output')
        self.assertEqual(stats.output_errors, 1)
        self.assertEqual(stats.errors, 5)
    
    def test_processing_stats_timing(self):
        """Test processing stats timing functionality"""
        stats = ProcessingStats()
        
        # Test timing methods
        stats.start_processing()
        self.assertIsNotNone(stats.start_time)
        
        import time
        time.sleep(0.1)  # Small delay for testing
        
        stats.end_processing()
        self.assertIsNotNone(stats.end_time)
        
        duration = stats.get_processing_duration()
        self.assertIsNotNone(duration)
        self.assertIn('s', duration)  # Should contain seconds
    
    def test_enhanced_summary_with_errors(self):
        """Test enhanced summary includes error breakdown and metrics"""
        stats = ProcessingStats()
        stats.total_fetched = 100
        stats.retained = 75
        stats.skipped_short = 15
        stats.skipped_duplicate = 5
        stats.skipped_system = 5
        
        # Add various error types
        stats.increment_error_type('fetch')
        stats.increment_error_type('fetch')
        stats.increment_error_type('timeout')
        stats.increment_error_type('processing')
        
        summary = stats.get_summary()
        
        # Should include basic stats
        self.assertIn('Total fetched: 100', summary)
        self.assertIn('Retained: 75', summary)
        self.assertIn('Total errors: 4', summary)
        
        # Should include error breakdown
        self.assertIn('Error breakdown:', summary)
        self.assertIn('fetch: 2', summary)
        self.assertIn('timeout: 1', summary)
        self.assertIn('processing: 1', summary)
        
        # Should include efficiency metrics
        self.assertIn('Retention rate: 75.0%', summary)
        self.assertIn('Error rate: 4.0%', summary)
    
    def test_quick_stats_format(self):
        """Test quick stats format for progress logging"""
        stats = ProcessingStats()
        stats.total_fetched = 50
        stats.retained = 40
        stats.errors = 3
        
        quick_stats = stats.get_quick_stats()
        self.assertEqual(quick_stats, "processed: 50, retained: 40, errors: 3")
    
    def test_timeout_error_handling_in_batch_processing(self):
        """Test timeout error handling during batch processing"""
        uids = ['uid1', 'uid2']
        
        # Mock fetch_message to raise TimeoutError for first UID
        def mock_fetch_with_timeout(uid):
            if uid == 'uid1':
                raise TimeoutError("Connection timeout")
            else:
                # Return valid message for second UID
                msg = email.message.EmailMessage()
                msg['Subject'] = 'Test Email'
                msg.set_content("This is a test email with sufficient content for processing and retention in the system which should be longer than twenty words to pass validation requirements.")
                return msg
        
        self.mock_imap_manager.fetch_message.side_effect = mock_fetch_with_timeout
        
        with patch('builtins.print'):  # Suppress error prints
            self.processor._process_batch(uids, 100)
        
        # Should handle timeout gracefully
        self.assertEqual(self.processor.stats.timeout_errors, 1)
        self.assertEqual(self.processor.stats.total_fetched, 1)  # Only second message processed
    
    def test_cache_error_handling_in_processing(self):
        """Test cache error handling during message processing"""
        uid = 'uid1'
        msg = email.message.EmailMessage()
        msg['Subject'] = 'Test Email'
        msg.set_content("This is a test email with sufficient content for processing and retention in the system which should be longer than twenty words to pass validation requirements.")
        
        # Mock cache manager to raise exception during content hash addition
        with patch.object(self.mock_cache_manager, 'add_content_hash', side_effect=Exception("Cache error")):
            with patch('builtins.print'):  # Suppress error prints
                result = self.processor._process_single_message(uid, msg)
        
        # Should still process message successfully despite cache error
        self.assertTrue(result)
        self.assertEqual(self.processor.stats.cache_errors, 1)
        self.assertEqual(self.processor.stats.retained, 1)
    
    def test_output_error_handling_in_processing(self):
        """Test output error handling during message processing"""
        uid = 'uid1'
        msg = email.message.EmailMessage()
        msg['Subject'] = 'Test Email'
        msg.set_content("This is a test email with sufficient content for processing and retention in the system which should be longer than twenty words to pass validation requirements.")
        
        # Mock output writer to raise exception during content writing
        with patch.object(self.mock_output_writer, 'write_content', side_effect=Exception("Output error")):
            with patch('builtins.print'):  # Suppress error prints
                result = self.processor._process_single_message(uid, msg)
        
        # Should still process message successfully despite output error
        self.assertTrue(result)
        self.assertEqual(self.processor.stats.output_errors, 1)
        self.assertEqual(self.processor.stats.retained, 1)
    
    def test_enhanced_progress_logging_with_rate(self):
        """Test enhanced progress logging includes processing rate"""
        uids = ['uid1', 'uid2']
        
        # Mock fetch_message to return valid messages
        mock_msg = email.message.EmailMessage()
        mock_msg['Subject'] = 'Test'
        mock_msg.set_content("This is a test email with sufficient content for processing and retention in the system which should be longer than twenty words to pass validation requirements.")
        self.mock_imap_manager.fetch_message.return_value = mock_msg
        
        # Mock _process_single_message to avoid actual processing but simulate success
        with patch.object(self.processor, '_process_single_message', return_value=True):
            with patch('builtins.print') as mock_print:
                # Use small progress interval to trigger logging
                self.processor._process_batch(uids, 1)
        
        # Should log progress with processing rate
        progress_calls = [str(call) for call in mock_print.call_args_list]
        rate_logged = any('processing rate:' in call for call in progress_calls)
        self.assertTrue(rate_logged, "Progress logging should include processing rate")
    
    def test_batch_processing_continues_after_errors(self):
        """Test that batch processing continues after individual message errors"""
        uids = ['uid1', 'uid2', 'uid3']
        
        # Mock fetch_message to fail for middle UID
        def mock_fetch_with_error(uid):
            if uid == 'uid2':
                raise Exception("Fetch error")
            else:
                msg = email.message.EmailMessage()
                msg['Subject'] = 'Test Email'
                msg.set_content("This is a test email with sufficient content for processing and retention in the system which should be longer than twenty words to pass validation requirements.")
                return msg
        
        self.mock_imap_manager.fetch_message.side_effect = mock_fetch_with_error
        
        with patch('builtins.print'):  # Suppress error prints
            self.processor._process_batch(uids, 100)
        
        # Should process 2 messages successfully despite 1 error
        self.assertEqual(self.processor.stats.total_fetched, 2)
        self.assertEqual(self.processor.stats.fetch_errors, 1)
    
    def test_comprehensive_process_emails_error_scenarios(self):
        """Test comprehensive error handling in process_emails method"""
        # Test cache loading error
        with patch.object(self.mock_cache_manager, 'load_cache', side_effect=Exception("Cache load error")):
            with patch.object(self.mock_imap_manager, 'fetch_message_uids', return_value=[['uid1']]):
                with patch.object(self.mock_imap_manager, 'fetch_message') as mock_fetch:
                    mock_msg = email.message.EmailMessage()
                    mock_msg.set_content("Test content")
                    mock_fetch.return_value = mock_msg
                    
                    with patch('builtins.print'):  # Suppress error prints
                        stats = self.processor.process_emails()
        
        # Should handle cache loading error gracefully
        self.assertEqual(stats.cache_errors, 1)
    
    def test_enhanced_message_preview_format(self):
        """Test enhanced message preview includes UID and better formatting"""
        # Add test messages to processor
        self.processor.processed_messages = [
            {
                'uid': 'uid123',
                'subject': 'Test Subject',
                'date': 'Mon, 1 Jan 2024 12:00:00',
                'content': 'This is test content for preview',
                'word_count': 6
            }
        ]
        
        with patch('builtins.print') as mock_print:
            self.processor._show_message_preview()
        
        # Check that preview includes UID and proper formatting
        preview_output = '\n'.join(str(call) for call in mock_print.call_args_list)
        self.assertIn('UID: uid123', preview_output)
        self.assertIn('Word count: 6', preview_output)
        self.assertIn('=' * 80, preview_output)  # Enhanced separator


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
        self.assertIn("Total errors: 5", summary)  # Updated to match new format
        self.assertIn("Retention rate: 65.0%", summary)  # New enhanced metric
        self.assertIn("Error rate: 5.0%", summary)  # New enhanced metric


if __name__ == '__main__':
    unittest.main() 