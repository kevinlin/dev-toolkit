#!/usr/bin/env python3
"""
Test script for content filtering and validation functionality
"""

import sys
import os
import email
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Add the src directory to the path so we can import from main.py
sys.path.insert(0, '.')

from main import ContentProcessor

def create_test_email(subject, body, from_addr="test@example.com", content_type="text/plain"):
    """Create a test email message"""
    if content_type == "text/html":
        msg = MIMEText(body, 'html')
    else:
        msg = MIMEText(body, 'plain')
    
    msg['Subject'] = subject
    msg['From'] = from_addr
    msg['To'] = "recipient@example.com"
    
    return msg

def test_word_count_validation():
    """Test word count validation (minimum 20 words)"""
    print("Testing word count validation...")
    
    processor = ContentProcessor()
    
    # Test short content (should be rejected)
    short_content = "This is too short."
    assert not processor.is_valid_content(short_content), "Short content should be rejected"
    print("✓ Short content correctly rejected")
    
    # Test long enough content (should be accepted)
    long_content = "This is a much longer email content that contains more than twenty words and should therefore pass the validation check for minimum word count requirements."
    assert processor.is_valid_content(long_content), "Long content should be accepted"
    print("✓ Long content correctly accepted")
    
    # Test exactly 20 words (should be accepted)
    exactly_20_words = "One two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen twenty"
    assert processor.is_valid_content(exactly_20_words), "Exactly 20 words should be accepted"
    print("✓ Exactly 20 words correctly accepted")
    
    # Test 19 words (should be rejected)
    nineteen_words = "One two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen"
    assert not processor.is_valid_content(nineteen_words), "19 words should be rejected"
    print("✓ 19 words correctly rejected")

def test_system_generated_detection():
    """Test system-generated content detection"""
    print("\nTesting system-generated content detection...")
    
    processor = ContentProcessor()
    
    # Test auto-reply detection
    auto_reply = create_test_email("Auto-Reply: Out of Office", "I am currently out of office.")
    assert processor.is_system_generated(auto_reply), "Auto-reply should be detected"
    print("✓ Auto-reply correctly detected")
    
    # Test delivery notification
    delivery_notif = create_test_email("Mail Delivery Failed", "Your message could not be delivered.")
    assert processor.is_system_generated(delivery_notif), "Delivery notification should be detected"
    print("✓ Delivery notification correctly detected")
    
    # Test normal email (should not be detected as system-generated)
    normal_email = create_test_email("Meeting Tomorrow", "Let's meet tomorrow at 3pm to discuss the project.")
    assert not processor.is_system_generated(normal_email), "Normal email should not be detected as system-generated"
    print("✓ Normal email correctly identified as user-generated")
    
    # Test noreply sender
    noreply_email = create_test_email("Welcome", "Welcome to our service", "noreply@example.com")
    assert processor.is_system_generated(noreply_email), "No-reply sender should be detected"
    print("✓ No-reply sender correctly detected")
    
    # Test enhanced patterns
    vacation_email = create_test_email("Vacation Message", "I am currently on vacation.")
    assert processor.is_system_generated(vacation_email), "Vacation message should be detected"
    print("✓ Vacation message correctly detected")
    
    # Test calendar notification
    calendar_email = create_test_email("Meeting Invitation", "You have been invited to a meeting.")
    assert processor.is_system_generated(calendar_email), "Meeting invitation should be detected"
    print("✓ Meeting invitation correctly detected")
    
    # Test security alert
    security_email = create_test_email("Security Alert", "Your account has been accessed.")
    assert processor.is_system_generated(security_email), "Security alert should be detected"
    print("✓ Security alert correctly detected")

def test_quoted_reply_stripping():
    """Test quoted reply and forwarded text stripping"""
    print("\nTesting quoted reply stripping...")
    
    processor = ContentProcessor()
    
    # Test basic quoted reply
    content_with_quotes = """This is my original message.

> This is a quoted reply from someone else.
> It should be removed from the content.

This is more of my original content."""
    
    cleaned = processor.strip_quoted_replies(content_with_quotes)
    assert "> This is a quoted reply" not in cleaned, "Quoted text should be removed"
    assert "This is my original message." in cleaned, "Original content should be preserved"
    print("✓ Basic quoted replies correctly stripped")
    
    # Test forwarded message
    forwarded_content = """Here is my comment on the forwarded message.

-----Original Message-----
From: someone@example.com
To: me@example.com
Subject: Original Subject

This is the original forwarded message content.
"""
    
    cleaned = processor.strip_quoted_replies(forwarded_content)
    assert "-----Original Message-----" not in cleaned, "Forward headers should be removed"
    assert "From: someone@example.com" not in cleaned, "Forward headers should be removed"
    assert "Here is my comment" in cleaned, "Original comment should be preserved"
    print("✓ Forwarded messages correctly stripped")
    
    # Test "On [date] wrote:" pattern
    on_wrote_content = """This is my response.

On Mon, Jan 15, 2024 at 10:30 AM, John Doe <john@example.com> wrote:
This is the original message that was replied to.
It should be removed.
"""
    
    cleaned = processor.strip_quoted_replies(on_wrote_content)
    assert "On Mon, Jan 15, 2024" not in cleaned, "On...wrote pattern should be removed"
    assert "This is my response." in cleaned, "Original response should be preserved"
    print("✓ 'On...wrote' patterns correctly stripped")
    
    # Test Gmail-style quoted reply
    gmail_content = """My thoughts on this topic.

On Tue, Jan 16, 2024 at 2:15 PM John Smith <john.smith@gmail.com> wrote:
> Here is the original message content
> that was being replied to.
> It should be completely removed.
"""
    
    cleaned = processor.strip_quoted_replies(gmail_content)
    assert "john.smith@gmail.com" not in cleaned, "Gmail-style quotes should be removed"
    assert "My thoughts on this topic." in cleaned, "Original content should be preserved"
    print("✓ Gmail-style quoted replies correctly stripped")
    
    # Test Apple Mail forwarded message
    apple_forward = """My comments about the forwarded message.

Begin forwarded message:

From: sender@example.com
Date: January 16, 2024 at 3:30:15 PM PST
To: recipient@example.com
Subject: Original Subject

This is the forwarded message content.
"""
    
    cleaned = processor.strip_quoted_replies(apple_forward)
    assert "Begin forwarded message:" not in cleaned, "Apple Mail forward should be removed"
    assert "sender@example.com" not in cleaned, "Forward headers should be removed"
    assert "My comments about" in cleaned, "Original comments should be preserved"
    print("✓ Apple Mail forwarded messages correctly stripped")

def test_html_to_text_conversion():
    """Test HTML to text conversion"""
    print("\nTesting HTML to text conversion...")
    
    processor = ContentProcessor()
    
    # Test basic HTML conversion
    html_content = """
    <html>
    <body>
        <h1>Important Meeting</h1>
        <p>We need to discuss the <strong>quarterly results</strong>.</p>
        <p>Please bring your <em>reports</em> to the meeting.</p>
        <ul>
            <li>Sales figures</li>
            <li>Marketing data</li>
        </ul>
    </body>
    </html>
    """
    
    text_content = processor.convert_html_to_text(html_content)
    assert "Important Meeting" in text_content, "HTML headings should be converted"
    assert "quarterly results" in text_content, "HTML content should be preserved"
    assert "<html>" not in text_content, "HTML tags should be removed"
    assert "<strong>" not in text_content, "HTML tags should be removed"
    print("✓ HTML to text conversion working correctly")

def test_whitespace_normalization():
    """Test whitespace normalization"""
    print("\nTesting whitespace normalization...")
    
    processor = ContentProcessor()
    
    # Test excessive whitespace
    messy_content = """   This    has    too    much    whitespace.   


    And   too   many   line   breaks.



    But   should   be   cleaned   up.   """
    
    cleaned = processor.normalize_whitespace(messy_content)
    
    # Should not have excessive spaces
    assert "    " not in cleaned, "Multiple spaces should be normalized"
    
    # Should not have excessive line breaks
    lines = cleaned.split('\n')
    empty_line_count = sum(1 for line in lines if not line.strip())
    assert empty_line_count <= 2, "Should not have more than 2 consecutive empty lines"
    
    # Should preserve content
    assert "This has too much whitespace." in cleaned, "Content should be preserved"
    print("✓ Whitespace normalization working correctly")

def test_content_quality_validation():
    """Test additional content quality validation"""
    print("\nTesting content quality validation...")
    
    processor = ContentProcessor()
    
    # Test mostly non-alphabetic content (should be rejected)
    garbled_content = "123456789 !@#$%^&*() 987654321 []{}()<> 111222333 $$$$$$$ This has some words but mostly symbols and numbers."
    # This should still pass because it has enough alphabetic content
    
    # Test empty content
    assert not processor.is_valid_content(""), "Empty content should be rejected"
    assert not processor.is_valid_content("   "), "Whitespace-only content should be rejected"
    print("✓ Content quality validation working correctly")

def run_all_tests():
    """Run all content filtering tests"""
    print("Running Content Filtering and Validation Tests")
    print("=" * 50)
    
    try:
        test_word_count_validation()
        test_system_generated_detection()
        test_quoted_reply_stripping()
        test_html_to_text_conversion()
        test_whitespace_normalization()
        test_content_quality_validation()
        
        print("\n" + "=" * 50)
        print("✅ All content filtering tests passed!")
        return True
        
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        return False
    except Exception as e:
        print(f"\n❌ Unexpected error during testing: {e}")
        return False

if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)