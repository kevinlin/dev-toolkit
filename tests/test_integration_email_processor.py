#!/usr/bin/env python3
"""
Integration tests for EmailProcessor class
"""

import unittest
import email
from unittest.mock import patch, MagicMock
import sys
import os

# Add the parent directory to the path so we can import main
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import EmailProcessor, ProcessingStats, ContentProcessor


class TestEmailProcessorIntegration(unittest.TestCase):
    """Integration tests for EmailProcessor class"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.mock_imap_manager = MagicMock()
        self.processor = EmailProcessor(self.mock_imap_manager)
    
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


if __name__ == '__main__':
    unittest.main() 