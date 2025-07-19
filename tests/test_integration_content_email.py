#!/usr/bin/env python3
"""
Integration tests for ContentProcessor and EmailProcessor interaction
"""

import unittest
import email
from unittest.mock import patch, MagicMock
import sys
import os

# Add the parent directory to the path so we can import main
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import EmailProcessor, ContentProcessor


class TestContentProcessorEmailProcessorIntegration(unittest.TestCase):
    """Integration tests for ContentProcessor and EmailProcessor"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.mock_imap_manager = MagicMock()
        self.email_processor = EmailProcessor(self.mock_imap_manager)
    
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


if __name__ == '__main__':
    unittest.main()