#!/usr/bin/env python3
"""
Unit tests for enhanced ContentProcessor functionality
Tests opening greetings, signatures, and blank lines filtering
"""

import os
import sys
import unittest

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from content_processor import ContentProcessor


class TestContentProcessorEnhanced(unittest.TestCase):
    """Test enhanced content filtering functionality"""

    def setUp(self):
        """Set up test fixtures"""
        self.processor = ContentProcessor()

    def test_strip_opening_greetings_basic(self):
        """Test basic opening greeting removal"""
        content = """Hi Krishna,
I hope this email finds you well.
Please review the attached document.
Thanks!"""

        expected = """I hope this email finds you well.
Please review the attached document.
Thanks!"""

        result = self.processor.strip_opening_greetings(content)
        self.assertEqual(result, expected)

    def test_strip_opening_greetings_various_forms(self):
        """Test various forms of opening greetings"""
        test_cases = [
            ("Hello Ben,\nContent here", "Content here"),
            ("Dear Raina:\nContent here", "Content here"),
            ("Hi all,\nContent here", "Content here"),
            ("Dear Sir or Madam,\nContent here", "Content here"),
            ("Good morning team,\nContent here", "Content here"),
            ("Hi there!\nContent here", "Content here"),
            ("Hello\nContent here", "Content here"),
            ("Hey everyone,\nContent here", "Content here"),
        ]

        for input_content, expected in test_cases:
            with self.subTest(input_content=input_content):
                result = self.processor.strip_opening_greetings(input_content)
                self.assertEqual(result, expected)

    def test_strip_opening_greetings_multiple_names(self):
        """Test greeting removal with multiple names"""
        content = """Hi John and Jane,
This is the actual content.
More content here."""

        expected = """This is the actual content.
More content here."""

        result = self.processor.strip_opening_greetings(content)
        self.assertEqual(result, expected)

    def test_strip_opening_greetings_preserves_content(self):
        """Test that greetings within content are preserved"""
        content = """This is the main content.
Hi there, this is not a greeting line.
More content follows."""

        # Should preserve all content since no greeting at the beginning
        result = self.processor.strip_opening_greetings(content)
        self.assertEqual(result, content)

    def test_strip_signatures_kevin_lin(self):
        """Test Kevin Lin's specific signature removal"""
        content = """This is the email content.
I look forward to your response.

Best regards,
Kevin Lin"""

        expected = """This is the email content.
I look forward to your response."""

        result = self.processor.strip_signatures(content)
        self.assertEqual(result, expected)

    def test_strip_signatures_sincerely_yours(self):
        """Test Sincerely yours signature removal"""
        content = """Here's the important information.
Please let me know if you have questions.

Sincerely yours,
Kevin Lin"""

        expected = """Here's the important information.
Please let me know if you have questions."""

        result = self.processor.strip_signatures(content)
        self.assertEqual(result, expected)

    def test_strip_signatures_various_closings(self):
        """Test various signature closing removal"""
        test_cases = [
            ("Content here.\nBest regards,\nJohn", "Content here."),
            ("Content here.\nThanks,\nJane", "Content here."),
            ("Content here.\nRegards,\nBob", "Content here."),
            ("Content here.\nKind regards,\nAlice", "Content here."),
            ("Content here.\nYours truly,\nCharlie", "Content here."),
        ]

        # Test each case individually
        for input_content, expected in test_cases:
            with self.subTest(input_content=input_content):
                result = self.processor.strip_signatures(input_content)
                self.assertEqual(result, expected)

    def test_strip_signatures_mobile(self):
        """Test mobile signature removal"""
        content = """Important message content.
Call me when you get this.

Sent from my iPhone"""

        expected = """Important message content.
Call me when you get this."""

        result = self.processor.strip_signatures(content)
        self.assertEqual(result, expected)

    def test_normalize_whitespace_removes_blank_lines(self):
        """Test that blank lines are removed"""
        content = """Line one.

Line two.


Line three.

"""

        expected = """Line one.
Line two.
Line three."""

        result = self.processor.normalize_whitespace(content)
        self.assertEqual(result, expected)

    def test_normalize_whitespace_preserves_content(self):
        """Test that content lines are preserved while normalizing whitespace"""
        content = """  This  has    extra   spaces.
	This has tabs.
This is normal."""

        expected = """This has extra spaces.
This has tabs.
This is normal."""

        result = self.processor.normalize_whitespace(content)
        self.assertEqual(result, expected)

    def test_full_content_processing_chain(self):
        """Test the complete content processing chain"""
        content = """Hi Krishna,

Hope you're doing well!

This is the main content of the email.
It contains important information.

Back to original content.

Best regards,
Kevin Lin"""

        # Process through the complete chain
        result = content
        result = self.processor.strip_quoted_replies(result)
        result = self.processor.strip_opening_greetings(result)
        result = self.processor.strip_signatures(result)
        result = self.processor.normalize_whitespace(result)

        expected = """Hope you're doing well!
This is the main content of the email.
It contains important information.
Back to original content."""

        self.assertEqual(result, expected)

    def test_empty_content_handling(self):
        """Test that empty content is handled gracefully"""
        test_cases = [
            ("", ""),  # Empty string should return empty
            ("   ", ""),  # Whitespace only should normalize to empty
            ("\n\n\n", ""),  # Newlines only should normalize to empty
        ]

        for test_content, expected in test_cases:
            with self.subTest(content=repr(test_content)):
                # The first two methods should preserve the input as-is if not empty
                result_greetings = self.processor.strip_opening_greetings(test_content)
                result_signatures = self.processor.strip_signatures(test_content)

                # Only normalize_whitespace should clean up whitespace-only content
                result_whitespace = self.processor.normalize_whitespace(test_content)
                self.assertEqual(result_whitespace, expected)

                # For truly empty content, all methods should return empty
                if test_content == "":
                    self.assertEqual(result_greetings, "")
                    self.assertEqual(result_signatures, "")

    def test_signature_in_middle_preserved(self):
        """Test that signature-like content in the middle is preserved"""
        content = """This is the main content.
We discussed the best regards policy.
Kevin Lin mentioned this in the meeting.
More content follows.
Final thoughts here."""

        # Should preserve all content since signature patterns are not at the end
        result = self.processor.strip_signatures(content)
        self.assertEqual(result, content)

    def test_greeting_not_at_start_preserved(self):
        """Test that greeting-like content not at start is preserved"""
        content = """This is the actual content.
In the email, I said Hi Krishna to greet them.
The document mentioned something important.
More content here."""

        # Should preserve all content since greetings are not at the beginning
        result = self.processor.strip_opening_greetings(content)
        self.assertEqual(result, content)


if __name__ == '__main__':
    unittest.main()
