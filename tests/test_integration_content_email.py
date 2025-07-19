#!/usr/bin/env python3
"""
Integration tests for ContentProcessor and EmailProcessor interaction
"""

import unittest
import email
from unittest.mock import patch, MagicMock
import sys
import os

# Add the parent directory to the path so we can import email_exporter
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from email_exporter import EmailProcessor
from content_processor import ContentProcessor


class TestContentProcessorEmailProcessorIntegration(unittest.TestCase):
    """Integration tests for ContentProcessor and EmailProcessor"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.mock_imap_manager = MagicMock()
        self.email_processor = EmailProcessor(self.mock_imap_manager)
        self.content_processor = ContentProcessor()
    
    def create_test_message(self, subject, from_addr, content, content_type='text/plain'):
        """Helper to create test email messages"""
        msg = email.message.EmailMessage()
        msg['Subject'] = subject
        msg['From'] = from_addr
        msg['Date'] = 'Mon, 15 Jan 2024 10:30:00 +0000'
        
        if content_type == 'text/html':
            msg.set_content(content, subtype='html')
        else:
            msg.set_content(content)
        
        return msg
    
    def test_end_to_end_valid_message_processing(self):
        """Test complete processing flow for a valid message"""
        # Create a valid message with sufficient content
        content = """This is a comprehensive email message that contains more than twenty words to ensure it passes all validation checks and processing steps successfully. The content includes proper formatting and meaningful text that should be retained after processing."""
        
        msg = self.create_test_message(
            subject="Important Business Update",
            from_addr="colleague@company.com",
            content=content
        )
        
        # Process the message
        self.email_processor._process_single_message('12345', msg)
        
        # Verify message was retained
        self.assertEqual(self.email_processor.stats.retained, 1)
        self.assertEqual(self.email_processor.stats.skipped_system, 0)
        self.assertEqual(self.email_processor.stats.skipped_short, 0)
        self.assertEqual(self.email_processor.stats.errors, 0)
        
        # Verify processed message details
        self.assertEqual(len(self.email_processor.processed_messages), 1)
        processed = self.email_processor.processed_messages[0]
        
        self.assertEqual(processed['uid'], '12345')
        self.assertEqual(processed['subject'], 'Important Business Update')
        self.assertEqual(processed['date'], 'Mon, 15 Jan 2024 10:30:00 +0000')
        self.assertIn('comprehensive email message', processed['content'])
        self.assertGreater(processed['word_count'], 20)
    
    def test_end_to_end_system_message_filtering(self):
        """Test complete processing flow filters out system messages"""
        # Create a system-generated message
        msg = self.create_test_message(
            subject="Auto-Reply: Out of Office",
            from_addr="user@company.com",
            content="I am currently out of the office and will return on Monday. This is an automated response."
        )
        
        # Process the message
        self.email_processor._process_single_message('12346', msg)
        
        # Verify message was skipped as system-generated
        self.assertEqual(self.email_processor.stats.skipped_system, 1)
        self.assertEqual(self.email_processor.stats.retained, 0)
        self.assertEqual(len(self.email_processor.processed_messages), 0)
    
    def test_end_to_end_short_content_filtering(self):
        """Test complete processing flow filters out short content"""
        # Create a message with insufficient content
        msg = self.create_test_message(
            subject="Brief Note",
            from_addr="colleague@company.com",
            content="Thanks!"  # Too short
        )
        
        # Process the message
        self.email_processor._process_single_message('12347', msg)
        
        # Verify message was skipped as too short
        self.assertEqual(self.email_processor.stats.skipped_short, 1)
        self.assertEqual(self.email_processor.stats.retained, 0)
        self.assertEqual(len(self.email_processor.processed_messages), 0)
    
    def test_end_to_end_html_content_processing(self):
        """Test complete processing flow handles HTML content"""
        # Create an HTML message
        html_content = """
        <html>
        <body>
            <h1>Important Announcement</h1>
            <p>This is an <strong>important business announcement</strong> that contains 
            sufficient content to pass validation checks. The HTML formatting should be 
            converted to plain text while preserving the essential information and 
            maintaining readability for the end user.</p>
            <script>alert('This should be removed');</script>
        </body>
        </html>
        """
        
        msg = self.create_test_message(
            subject="HTML Newsletter",
            from_addr="marketing@company.com",
            content=html_content,
            content_type='text/html'
        )
        
        # Process the message
        self.email_processor._process_single_message('12348', msg)
        
        # Verify message was processed successfully
        self.assertEqual(self.email_processor.stats.retained, 1)
        self.assertEqual(len(self.email_processor.processed_messages), 1)
        
        processed = self.email_processor.processed_messages[0]
        
        # Verify HTML was converted to text
        self.assertNotIn('<html>', processed['content'])
        self.assertNotIn('<script>', processed['content'])
        self.assertIn('Important Announcement', processed['content'])
        self.assertIn('important business announcement', processed['content'])
    
    def test_end_to_end_multipart_message_processing(self):
        """Test complete processing flow handles multipart messages"""
        # Create a multipart message
        msg = email.message.EmailMessage()
        msg['Subject'] = 'Multipart Message'
        msg['From'] = 'sender@company.com'
        msg['Date'] = 'Mon, 15 Jan 2024 10:30:00 +0000'
        
        # Add text part
        text_content = """This is the plain text version of a multipart message that contains sufficient content for processing and validation. The text should be preferred over HTML content when both are available."""
        msg.set_content(text_content)
        
        # Add HTML part
        html_content = """<p>This is the <strong>HTML version</strong> that should be ignored when plain text is available.</p>"""
        msg.add_alternative(html_content, subtype='html')
        
        # Process the message
        self.email_processor._process_single_message('12349', msg)
        
        # Verify message was processed successfully
        self.assertEqual(self.email_processor.stats.retained, 1)
        self.assertEqual(len(self.email_processor.processed_messages), 1)
        
        processed = self.email_processor.processed_messages[0]
        
        # Verify plain text was preferred
        self.assertIn('plain text version', processed['content'])
        self.assertNotIn('<p>', processed['content'])
        self.assertNotIn('<strong>', processed['content'])
    
    def test_end_to_end_quoted_reply_removal(self):
        """Test complete processing flow removes quoted replies"""
        # Create a message with quoted content
        content_with_quotes = """This is my original response to the previous email thread.

I wanted to follow up on the discussion we had yesterday about the project timeline and deliverables.

On Mon, Jan 15, 2024 at 9:00 AM, Colleague <colleague@company.com> wrote:
> Thanks for the update on the project status.
> I'll review the documents and get back to you.
> 
> Best regards,
> Colleague

From: Manager <manager@company.com>
Sent: Monday, January 15, 2024 8:00 AM
Subject: Project Update

Please find the attached project timeline for your review."""
        
        msg = self.create_test_message(
            subject="Re: Project Timeline",
            from_addr="user@company.com",
            content=content_with_quotes
        )
        
        # Process the message
        self.email_processor._process_single_message('12350', msg)
        
        # Verify message was processed successfully
        self.assertEqual(self.email_processor.stats.retained, 1)
        self.assertEqual(len(self.email_processor.processed_messages), 1)
        
        processed = self.email_processor.processed_messages[0]
        
        # Verify quoted content was removed
        self.assertIn('original response', processed['content'])
        self.assertIn('follow up on the discussion', processed['content'])
        self.assertNotIn('> Thanks for the update', processed['content'])
        self.assertNotIn('From: Manager', processed['content'])
    
    def test_end_to_end_whitespace_normalization(self):
        """Test complete processing flow normalizes whitespace"""
        # Create a message with messy whitespace
        messy_content = """   This    message   has    lots   of    extra    whitespace   


        and    multiple    line    breaks    that    need    to    be    normalized    properly    for    


        better    readability    and    consistent    formatting    throughout    the    content    processing    pipeline.   """
        
        msg = self.create_test_message(
            subject="Messy Formatting",
            from_addr="user@company.com",
            content=messy_content
        )
        
        # Process the message
        self.email_processor._process_single_message('12351', msg)
        
        # Verify message was processed successfully
        self.assertEqual(self.email_processor.stats.retained, 1)
        self.assertEqual(len(self.email_processor.processed_messages), 1)
        
        processed = self.email_processor.processed_messages[0]
        
        # Verify whitespace was normalized
        self.assertNotIn('    ', processed['content'])  # No multiple spaces
        self.assertNotIn('\n\n\n', processed['content'])  # No excessive newlines
        self.assertIn('This message has lots', processed['content'])
        self.assertIn('better readability', processed['content'])
    
    def test_end_to_end_batch_processing(self):
        """Test complete batch processing flow"""
        # Create multiple test messages
        messages = [
            self.create_test_message("Valid Message 1", "user1@company.com", 
                                   "This is a valid message with sufficient content for processing and retention in the system. It contains more than twenty words to ensure proper validation and processing by the email content extraction system."),
            self.create_test_message("Auto-Reply: Out of Office", "user2@company.com", 
                                   "I am out of office"),  # System message
            self.create_test_message("Valid Message 2", "user3@company.com", 
                                   "Another valid message that should be processed and retained successfully by the email processing system. This message also contains sufficient content to pass all validation checks and quality requirements."),
            self.create_test_message("Short", "user4@company.com", "Too short"),  # Too short
        ]
        
        uids = ['1001', '1002', '1003', '1004']
        
        # Mock fetch_message to return our test messages
        self.mock_imap_manager.fetch_message.side_effect = messages
        
        # Process the batch
        self.email_processor._process_batch(uids, 100)
        
        # Verify batch processing results
        self.assertEqual(self.email_processor.stats.total_fetched, 4)
        self.assertEqual(self.email_processor.stats.retained, 2)  # 2 valid messages
        self.assertEqual(self.email_processor.stats.skipped_system, 1)  # 1 system message
        self.assertEqual(self.email_processor.stats.skipped_short, 1)  # 1 short message
        self.assertEqual(self.email_processor.stats.errors, 0)
        
        # Verify processed messages
        self.assertEqual(len(self.email_processor.processed_messages), 2)
        
        # Check that the right messages were retained
        subjects = [msg['subject'] for msg in self.email_processor.processed_messages]
        self.assertIn('Valid Message 1', subjects)
        self.assertIn('Valid Message 2', subjects)
        self.assertNotIn('Auto-Reply: Out of Office', subjects)
        self.assertNotIn('Short', subjects)

    def test_content_duplicate_detection_basic(self):
        """Test basic content duplicate detection during email processing"""
        # Create two emails with identical content
        identical_content = "This is an identical email body content for testing duplicate detection with enough words to pass validation."
        
        email1 = self.create_test_message("subject1", "colleague@company.com", identical_content)
        email2 = self.create_test_message("subject2", "colleague@company.com", identical_content)  # Different subject, same content
        
        # Test that content processor detects duplicates
        hash1 = self.content_processor.hash_content(identical_content)
        hash2 = self.content_processor.hash_content(identical_content)
        
        self.assertEqual(hash1, hash2)
        
        # Test with existing hashes
        existing_hashes = {hash1}
        self.assertTrue(self.content_processor.is_content_duplicate(identical_content, existing_hashes))
    
    def test_content_duplicate_with_formatting_differences(self):
        """Test that content duplicates are detected despite formatting differences"""
        content1 = "This is an email with  extra   spaces\n\n\nand multiple line breaks for testing purposes."
        content2 = "This is an email with extra spaces\nand multiple line breaks for testing purposes."
        
        # Should produce same hash after normalization
        hash1 = self.content_processor.hash_content(content1)
        hash2 = self.content_processor.hash_content(content2)
        
        self.assertEqual(hash1, hash2)
        
        # Test duplicate detection
        existing_hashes = {hash1}
        self.assertTrue(self.content_processor.is_content_duplicate(content2, existing_hashes))
    
    def test_content_duplicate_case_insensitive(self):
        """Test that content duplicate detection is case insensitive"""
        content1 = "This Is An Email With Different Case Letters For Testing Duplicate Detection Properly."
        content2 = "this is an email with different case letters for testing duplicate detection properly."
        
        # Should produce same hash regardless of case
        hash1 = self.content_processor.hash_content(content1)
        hash2 = self.content_processor.hash_content(content2)
        
        self.assertEqual(hash1, hash2)
        
        # Test duplicate detection
        existing_hashes = {hash1}
        self.assertTrue(self.content_processor.is_content_duplicate(content2, existing_hashes))
    
    def test_content_duplicate_with_quoted_replies(self):
        """Test content duplicate detection after quoted reply stripping"""
        original_content = "This is the original email content for testing duplicate detection after reply stripping."
        
        content_with_reply = f"""{original_content}

On 2024-01-15, someone wrote:
> This is a quoted reply that should be stripped
> when processing the email content
"""
        
        # Both should produce same hash after processing
        hash1 = self.content_processor.hash_content(original_content)
        
        # Process content with reply through full pipeline
        cleaned_content = self.content_processor.strip_quoted_replies(content_with_reply)
        normalized_content = self.content_processor.normalize_whitespace(cleaned_content)
        hash2 = self.content_processor.hash_content(normalized_content)
        
        self.assertEqual(hash1, hash2)
        
        # Test duplicate detection
        existing_hashes = {hash1}
        self.assertTrue(self.content_processor.is_content_duplicate(normalized_content, existing_hashes))
    
    def test_non_duplicate_content(self):
        """Test that genuinely different content is not detected as duplicate"""
        content1 = "This is the first unique email content for testing purposes with sufficient words."
        content2 = "This is the second unique email content for testing purposes with sufficient words."
        
        # Should produce different hashes
        hash1 = self.content_processor.hash_content(content1)
        hash2 = self.content_processor.hash_content(content2)
        
        self.assertNotEqual(hash1, hash2)
        
        # Test duplicate detection
        existing_hashes = {hash1}
        self.assertFalse(self.content_processor.is_content_duplicate(content2, existing_hashes))
    
    def test_content_hash_stability(self):
        """Test that content hashes remain stable across multiple calls"""
        content = "This is a test email content for verifying hash stability across multiple generations."
        
        # Generate multiple hashes
        hashes = [self.content_processor.hash_content(content) for _ in range(5)]
        
        # All hashes should be identical
        for hash_val in hashes:
            self.assertEqual(hash_val, hashes[0])
            self.assertEqual(len(hash_val), 64)  # SHA-256 hash length
    
    def test_empty_content_handling(self):
        """Test handling of empty or invalid content in hashing"""
        self.assertEqual(self.content_processor.hash_content(""), "")
        self.assertEqual(self.content_processor.hash_content(None), "")
        self.assertEqual(self.content_processor.hash_content("   \n\t   "), "")
        
        # Test duplicate detection with empty content
        existing_hashes = {"somehash"}
        self.assertFalse(self.content_processor.is_content_duplicate("", existing_hashes))
        self.assertFalse(self.content_processor.is_content_duplicate(None, existing_hashes))


if __name__ == '__main__':
    unittest.main()