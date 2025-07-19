#!/usr/bin/env python3
"""
Integration tests for EmailProcessor class
"""

import unittest
import email
from unittest.mock import patch, MagicMock
import sys
import os
import tempfile
import shutil

# Add the parent directory to the path so we can import main
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import EmailProcessor, ProcessingStats, ContentProcessor, CacheManager


class TestEmailProcessorIntegration(unittest.TestCase):
    """Integration tests for EmailProcessor class"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.mock_imap_manager = MagicMock()
        self.provider = 'gmail'  # Provider for CacheManager
        self.test_dir = tempfile.mkdtemp()  # Test directory for CacheManager
        self.processor = EmailProcessor(self.mock_imap_manager)
    
    def tearDown(self):
        """Clean up test fixtures"""
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
    
    def _create_mock_email_message(self, uid: str, subject: str = "Test Subject", 
                                 body: str = "This is a test email with more than twenty words to pass validation. It contains meaningful content for testing purposes."):
        """Create a mock email message for testing"""
        msg = email.message.EmailMessage()
        msg['Subject'] = subject
        msg['Date'] = 'Mon, 01 Jan 2024 12:00:00 +0000'
        msg['From'] = 'test@example.com'
        msg['To'] = 'recipient@example.com'
        msg.set_content(body)
        return msg
    
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
    
    def test_full_email_processing_workflow(self):
        """Test full email processing workflow with minimal mocking"""
        # Create realistic test messages
        messages = []
        
        # Valid message
        valid_msg = email.message.EmailMessage()
        valid_msg['Subject'] = 'Project Discussion'
        valid_msg['From'] = 'colleague@company.com'
        valid_msg['Date'] = 'Mon, 15 Jan 2024 10:30:00 +0000'
        valid_msg.set_content(
            "Hi team, I wanted to discuss our upcoming project timeline and deliverables. "
            "We need to ensure that all components are properly tested before the release. "
            "The client has specific requirements that we need to address in the next iteration. "
            "Please review the attached documentation and provide feedback by end of week."
        )
        messages.append(valid_msg)
        
        # System-generated message
        system_msg = email.message.EmailMessage()
        system_msg['Subject'] = 'Auto-Reply: Out of Office'
        system_msg['From'] = 'user@company.com'
        system_msg['Date'] = 'Mon, 15 Jan 2024 11:00:00 +0000'
        system_msg.set_content("I am currently out of office and will return on Monday.")
        messages.append(system_msg)
        
        # Short message (insufficient content)
        short_msg = email.message.EmailMessage()
        short_msg['Subject'] = 'Quick Update'
        short_msg['From'] = 'manager@company.com'
        short_msg['Date'] = 'Mon, 15 Jan 2024 12:00:00 +0000'
        short_msg.set_content("Thanks!")
        messages.append(short_msg)
        
        # Setup mocks for IMAP manager
        uids = ['msg1', 'msg2', 'msg3']
        self.mock_imap_manager.fetch_message_uids.return_value = [uids]
        self.mock_imap_manager.fetch_message.side_effect = messages
        
        # Process emails (minimal mocking - let ContentProcessor work naturally)
        with patch('builtins.print'):  # Suppress output
            stats = self.processor.process_emails()
        
        # Verify results
        self.assertEqual(stats.total_fetched, 3)
        self.assertEqual(stats.retained, 1)  # Only the valid message
        self.assertEqual(stats.skipped_system, 1)  # Auto-reply message
        self.assertEqual(stats.skipped_short, 1)  # Short message
        self.assertEqual(stats.errors, 0)
        
        # Verify processed message details
        self.assertEqual(len(self.processor.processed_messages), 1)
        processed = self.processor.processed_messages[0]
        self.assertEqual(processed['uid'], 'msg1')
        self.assertEqual(processed['subject'], 'Project Discussion')
        self.assertIn('project timeline', processed['content'])
        self.assertGreater(processed['word_count'], 20)
    
    def test_html_email_processing_integration(self):
        """Test integration with HTML email processing"""
        # Create HTML email message
        html_msg = email.message.EmailMessage()
        html_msg['Subject'] = 'Newsletter Update'
        html_msg['From'] = 'newsletter@company.com'
        html_msg['Date'] = 'Mon, 15 Jan 2024 14:00:00 +0000'
        
        html_content = """
        <html>
        <body>
            <h1>Important Company Update</h1>
            <p>We are pleased to announce several important updates to our services and policies. 
            These changes will improve our customer experience and streamline our operations. 
            Please take the time to review these changes carefully as they may affect your account.</p>
            <ul>
                <li>Enhanced security features</li>
                <li>Improved user interface</li>
                <li>Better customer support</li>
            </ul>
            <p>If you have any questions, please contact our support team.</p>
        </body>
        </html>
        """
        html_msg.set_content(html_content, subtype='html')
        
        # Setup mocks
        self.mock_imap_manager.fetch_message_uids.return_value = [['html_msg']]
        self.mock_imap_manager.fetch_message.return_value = html_msg
        
        # Process the HTML email
        with patch('builtins.print'):
            stats = self.processor.process_emails()
        
        # Verify processing
        self.assertEqual(stats.retained, 1)
        self.assertEqual(len(self.processor.processed_messages), 1)
        
        processed = self.processor.processed_messages[0]
        content = processed['content']
        
        # Verify HTML was converted to text
        self.assertNotIn('<html>', content)
        self.assertNotIn('<body>', content)
        self.assertNotIn('<h1>', content)
        self.assertIn('Important Company Update', content)
        self.assertIn('Enhanced security features', content)
        self.assertGreater(processed['word_count'], 20)
    
    def test_multipart_email_processing_integration(self):
        """Test integration with multipart email processing"""
        # Create multipart email with both text and HTML parts
        multipart_msg = email.message.EmailMessage()
        multipart_msg['Subject'] = 'Team Meeting Notes'
        multipart_msg['From'] = 'organizer@company.com'
        multipart_msg['Date'] = 'Mon, 15 Jan 2024 16:00:00 +0000'
        
        # Add plain text part
        text_content = """
        Meeting Notes - January 15, 2024
        
        Attendees: John, Sarah, Mike, Lisa
        
        Agenda Items Discussed:
        1. Project status update and milestone review
        2. Resource allocation for next quarter planning
        3. Client feedback integration and response strategy
        4. Team development goals and training opportunities
        
        Action Items:
        - Complete code review by Wednesday
        - Schedule client presentation for next week
        - Update project documentation and timeline
        """
        multipart_msg.set_content(text_content)
        
        # Add HTML part
        html_content = """
        <html><body>
        <h2>Meeting Notes - January 15, 2024</h2>
        <p><strong>Attendees:</strong> John, Sarah, Mike, Lisa</p>
        <h3>Agenda Items:</h3>
        <ol>
            <li>Project status update</li>
            <li>Resource allocation</li>
            <li>Client feedback</li>
            <li>Team development</li>
        </ol>
        </body></html>
        """
        multipart_msg.add_alternative(html_content, subtype='html')
        
        # Setup mocks
        self.mock_imap_manager.fetch_message_uids.return_value = [['multipart_msg']]
        self.mock_imap_manager.fetch_message.return_value = multipart_msg
        
        # Process the multipart email
        with patch('builtins.print'):
            stats = self.processor.process_emails()
        
        # Verify processing
        self.assertEqual(stats.retained, 1)
        self.assertEqual(len(self.processor.processed_messages), 1)
        
        processed = self.processor.processed_messages[0]
        content = processed['content']
        
        # Should prefer plain text over HTML
        self.assertIn('Meeting Notes - January 15, 2024', content)
        self.assertIn('Attendees: John, Sarah, Mike, Lisa', content)
        self.assertIn('Action Items:', content)
        
        # Should not contain HTML tags
        self.assertNotIn('<html>', content)
        self.assertNotIn('<strong>', content)
        
        self.assertGreater(processed['word_count'], 20)

    def test_email_processing_with_content_deduplication(self):
        """Test that content-based deduplication works during email processing"""
        # Create cache manager for the test
        cache_manager = CacheManager(self.provider, self.test_dir)
        email_processor = EmailProcessor(self.mock_imap_manager, cache_manager)
        
        # Create two different emails with identical content (ensure more than 20 words)
        identical_content = "This is an identical email body content for testing duplicate detection with enough words to pass validation. We need to ensure there are more than twenty words in this content so it will not be filtered out as short content. This should be sufficient for testing purposes."
        
        email1 = self._create_mock_email_message("uid1", "Subject 1", identical_content)
        email2 = self._create_mock_email_message("uid2", "Subject 2", identical_content)  # Different UID, same content
        email3 = self._create_mock_email_message("uid3", "Subject 3", "This is completely different content for testing purposes with sufficient words to ensure it passes validation. We need to make sure this content has more than twenty words so it will be processed correctly by the email processor.")
        
        # Set up batch processing
        test_batch = ['uid1', 'uid2', 'uid3']
        self.mock_imap_manager.fetch_message_uids.return_value = [test_batch]
        
        def mock_fetch_message(uid):
            if uid == 'uid1':
                return email1
            elif uid == 'uid2':
                return email2
            elif uid == 'uid3':
                return email3
            return None
        
        self.mock_imap_manager.fetch_message.side_effect = mock_fetch_message
        
        # Process emails
        stats = email_processor.process_emails()
        
        # First email should be retained, second should be skipped as duplicate, third should be retained
        self.assertEqual(stats.total_fetched, 3)
        self.assertEqual(stats.retained, 2)  # uid1 and uid3 retained
        self.assertEqual(stats.skipped_duplicate, 1)  # uid2 skipped as content duplicate
        
        # Verify content hashes were added to cache
        content_hashes = cache_manager.get_content_hashes()
        self.assertEqual(len(content_hashes), 2)  # Two unique content pieces
    
    def test_content_deduplication_with_normalized_content(self):
        """Test content deduplication works with content that needs normalization"""
        cache_manager = CacheManager(self.provider, self.test_dir)
        email_processor = EmailProcessor(self.mock_imap_manager, cache_manager)
        
        # Create emails with same content but different formatting (ensure more than 20 words)
        base_content = "This is a test email with meaningful content for testing normalization purposes. We need to ensure there are more than twenty words in this content so it will not be filtered out as short content by the validation logic."
        content1 = base_content
        content2 = f"  {base_content}  \n\n\n"  # Extra whitespace and line breaks
        content3 = base_content.upper()  # Different case
        
        email1 = self._create_mock_email_message("uid1", "Subject 1", content1)
        email2 = self._create_mock_email_message("uid2", "Subject 2", content2)
        email3 = self._create_mock_email_message("uid3", "Subject 3", content3)
        
        test_batch = ['uid1', 'uid2', 'uid3']
        self.mock_imap_manager.fetch_message_uids.return_value = [test_batch]
        
        def mock_fetch_message(uid):
            if uid == 'uid1':
                return email1
            elif uid == 'uid2':
                return email2
            elif uid == 'uid3':
                return email3
            return None
        
        self.mock_imap_manager.fetch_message.side_effect = mock_fetch_message
        
        # Process emails
        stats = email_processor.process_emails()
        
        # Only first email should be retained, others should be detected as duplicates
        self.assertEqual(stats.total_fetched, 3)
        self.assertEqual(stats.retained, 1)  # Only uid1 retained
        self.assertEqual(stats.skipped_duplicate, 2)  # uid2 and uid3 skipped as duplicates
        
        # Should only have one unique content hash
        content_hashes = cache_manager.get_content_hashes()
        self.assertEqual(len(content_hashes), 1)
    
    def test_content_deduplication_with_quoted_replies(self):
        """Test content deduplication after quoted reply stripping"""
        cache_manager = CacheManager(self.provider, self.test_dir)
        email_processor = EmailProcessor(self.mock_imap_manager, cache_manager)
        
        # Create emails with same core content but different quoted sections (ensure more than 20 words)
        core_content = "This is the original email content that should be detected as duplicate after stripping quotes. We need to ensure there are more than twenty words in this content so it will not be filtered out as short content during validation."
        
        content1 = core_content
        content2 = f"""{core_content}

On 2024-01-15, someone wrote:
> This is a quoted reply that should be stripped
> when processing the email content
"""
        content3 = f"""{core_content}

From: colleague@company.com
Subject: Re: Test
Date: Mon, 15 Jan 2024

> Another style of quoted content
> that should also be stripped
"""
        
        email1 = self._create_mock_email_message("uid1", "Subject 1", content1)
        email2 = self._create_mock_email_message("uid2", "Subject 2", content2)
        email3 = self._create_mock_email_message("uid3", "Subject 3", content3)
        
        test_batch = ['uid1', 'uid2', 'uid3']
        self.mock_imap_manager.fetch_message_uids.return_value = [test_batch]
        
        def mock_fetch_message(uid):
            if uid == 'uid1':
                return email1
            elif uid == 'uid2':
                return email2
            elif uid == 'uid3':
                return email3
            return None
        
        self.mock_imap_manager.fetch_message.side_effect = mock_fetch_message
        
        # Process emails
        stats = email_processor.process_emails()
        
        # Only first email should be retained after quote stripping reveals duplicates
        self.assertEqual(stats.total_fetched, 3)
        self.assertEqual(stats.retained, 1)  # Only uid1 retained
        self.assertEqual(stats.skipped_duplicate, 2)  # uid2 and uid3 detected as duplicates
        
        # Should only have one unique content hash
        content_hashes = cache_manager.get_content_hashes()
        self.assertEqual(len(content_hashes), 1)
    
    def test_mixed_uid_and_content_deduplication(self):
        """Test that both UID-based and content-based deduplication work together"""
        cache_manager = CacheManager(self.provider, self.test_dir)
        
        # Pre-populate cache with some UIDs and content hashes
        cache_manager.mark_processed('uid1')  # UID-based duplicate
        existing_content = "This content is already in cache for testing purposes with sufficient words for validation. We need to ensure there are more than twenty words in this content so it will not be filtered out as short content."
        # We'll add the content hash manually below
        
        # Add content hash manually for testing
        content_processor = ContentProcessor()
        existing_hash = content_processor.hash_content(existing_content)
        cache_manager.add_content_hash(existing_hash)
        
        email_processor = EmailProcessor(self.mock_imap_manager, cache_manager)
        
        # Create test emails
        email1 = self._create_mock_email_message("uid1", "Subject 1", "Some content for testing with enough words for validation. We need to ensure there are more than twenty words in this content so it will not be filtered out as short content.")  # UID duplicate
        email2 = self._create_mock_email_message("uid2", "Subject 2", existing_content)  # Content duplicate
        email3 = self._create_mock_email_message("uid3", "Subject 3", "Unique content for testing with enough words for validation. We need to ensure there are more than twenty words in this content so it will not be filtered out as short content.")  # Unique
        
        test_batch = ['uid1', 'uid2', 'uid3']
        self.mock_imap_manager.fetch_message_uids.return_value = [test_batch]
        
        def mock_fetch_message(uid):
            if uid == 'uid1':
                return email1
            elif uid == 'uid2':
                return email2
            elif uid == 'uid3':
                return email3
            return None
        
        self.mock_imap_manager.fetch_message.side_effect = mock_fetch_message
        
        # Process emails
        stats = email_processor.process_emails()
        
        # uid1 should be skipped as UID duplicate (before fetch)
        # uid2 should be skipped as content duplicate
        # uid3 should be retained
        self.assertEqual(stats.total_fetched, 2)  # uid1 not fetched due to UID cache
        self.assertEqual(stats.retained, 1)  # Only uid3 retained
        self.assertEqual(stats.skipped_duplicate, 2)  # uid1 (UID) + uid2 (content)
        
        # Verify final cache state
        self.assertTrue(cache_manager.is_processed('uid1'))
        self.assertTrue(cache_manager.is_processed('uid3'))
        self.assertFalse(cache_manager.is_processed('uid2'))  # Not marked as processed since skipped as content duplicate


if __name__ == '__main__':
    unittest.main() 