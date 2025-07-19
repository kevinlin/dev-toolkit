#!/usr/bin/env python3
"""
Integration test for content filtering within the email processing pipeline
"""

import sys
import email
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Add the parent directory to the path so we can import from main.py
sys.path.insert(0, '..')

from main import ContentProcessor, ProcessingStats

def create_test_message(subject, body, from_addr="test@example.com", content_type="text/plain"):
    """Create a test email message"""
    if content_type == "text/html":
        msg = MIMEText(body, 'html')
    else:
        msg = MIMEText(body, 'plain')
    
    msg['Subject'] = subject
    msg['From'] = from_addr
    msg['To'] = "recipient@example.com"
    msg['Date'] = "Mon, 15 Jan 2024 10:30:00 +0000"
    
    return msg

def test_email_processing_pipeline():
    """Test the complete email processing pipeline with filtering"""
    print("Testing email processing pipeline with content filtering...")
    
    processor = ContentProcessor()
    stats = ProcessingStats()
    processed_messages = []
    
    # Create test messages with different characteristics
    test_messages = [
        # Valid message (should be retained)
        create_test_message(
            "Project Update", 
            "Hi team, I wanted to provide an update on our current project status. We have made significant progress on the development phase and are on track to meet our deadline. The testing phase will begin next week and we expect to complete it by the end of the month. Please let me know if you have any questions or concerns."
        ),
        
        # System-generated message (should be skipped)
        create_test_message(
            "Auto-Reply: Out of Office", 
            "This is an automatic reply. I am currently out of office and will return on Monday.",
            "autoreply@company.com"
        ),
        
        # Short message (should be skipped)
        create_test_message(
            "Quick Note", 
            "Thanks for the update."
        ),
        
        # Message with quoted reply (content should be cleaned)
        create_test_message(
            "Re: Meeting Discussion",
            """I agree with your proposal for the meeting agenda. This is a comprehensive response that addresses all the points you raised in your previous message. I think we should definitely move forward with this approach as it aligns well with our strategic objectives.

On Mon, Jan 15, 2024 at 9:00 AM, John Doe <john@example.com> wrote:
> Let's discuss the quarterly budget in our next meeting.
> We should also review the project timelines.
> What do you think about scheduling it for next Friday?

Looking forward to the discussion and I believe this will be a productive meeting for everyone involved."""
        ),
        
        # HTML message (should be converted to text)
        create_test_message(
            "HTML Newsletter",
            """<html><body>
            <h1>Important Announcement</h1>
            <p>We are pleased to announce the launch of our new product line. This represents a significant milestone for our company and we believe it will provide great value to our customers.</p>
            <p>Key features include:</p>
            <ul>
                <li>Enhanced performance</li>
                <li>Improved user interface</li>
                <li>Better integration capabilities</li>
            </ul>
            <p>Thank you for your continued support.</p>
            </body></html>""",
            content_type="text/html"
        ),
        
        # Delivery notification (should be skipped)
        create_test_message(
            "Delivery Status Notification",
            "Your message could not be delivered to the following recipients.",
            "mailer-daemon@example.com"
        )
    ]
    
    # Process each message through the pipeline
    for i, message in enumerate(test_messages):
        uid = f"test_uid_{i}"
        
        try:
            # Check if message is system-generated first
            if processor.is_system_generated(message):
                stats.skipped_system += 1
                print(f"✓ Message {i+1}: Correctly identified as system-generated")
                continue
            
            # Extract and clean body content
            body_content = processor.extract_body_content(message)
            
            # Validate content quality
            if not processor.is_valid_content(body_content):
                stats.skipped_short += 1
                print(f"✓ Message {i+1}: Correctly rejected for insufficient content")
                continue
            
            # Store processed message with cleaned content
            stats.retained += 1
            processed_messages.append({
                'uid': uid,
                'subject': message.get('Subject', 'No Subject'),
                'content': body_content,
                'word_count': len(body_content.split())
            })
            print(f"✓ Message {i+1}: Successfully processed and retained")
                
        except Exception as e:
            print(f"❌ Error processing message {i+1}: {str(e)}")
            stats.errors += 1
    
    # Verify results
    print(f"\nProcessing Results:")
    print(f"  Total messages: {len(test_messages)}")
    print(f"  Retained: {stats.retained}")
    print(f"  Skipped (system): {stats.skipped_system}")
    print(f"  Skipped (short): {stats.skipped_short}")
    print(f"  Errors: {stats.errors}")
    
    # Verify expected results
    assert stats.retained == 3, f"Expected 3 retained messages, got {stats.retained}"
    assert stats.skipped_system == 2, f"Expected 2 system messages, got {stats.skipped_system}"
    assert stats.skipped_short == 1, f"Expected 1 short message, got {stats.skipped_short}"
    assert stats.errors == 0, f"Expected 0 errors, got {stats.errors}"
    
    # Verify content quality of retained messages
    for msg in processed_messages:
        assert len(msg['content'].split()) >= 20, f"Retained message should have >= 20 words"
        assert msg['content'].strip(), "Retained message should have non-empty content"
        
        # Check that quoted content was stripped from the reply message
        if "Re: Meeting Discussion" in msg['subject']:
            assert "john@example.com" not in msg['content'], "Quoted reply should be stripped"
            assert "I agree with your proposal" in msg['content'], "Original content should be preserved"
        
        # Check that HTML was converted to text
        if "HTML Newsletter" in msg['subject']:
            assert "<html>" not in msg['content'], "HTML tags should be removed"
            assert "Important Announcement" in msg['content'], "Content should be preserved"
            assert "Enhanced performance" in msg['content'], "List items should be preserved"
    
    print("✅ All integration tests passed!")
    return True

if __name__ == "__main__":
    try:
        success = test_email_processing_pipeline()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"❌ Integration test failed: {e}")
        sys.exit(1)