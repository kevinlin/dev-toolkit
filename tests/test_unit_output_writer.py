#!/usr/bin/env python3
"""
Unit tests for OutputWriter class

Tests file creation, content writing, output formatting, and error handling.
"""

import unittest
import os
import tempfile
import shutil
from unittest.mock import patch, mock_open
import datetime

# Import the OutputWriter class from email-exporter.py
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from email_exporter import OutputWriter


class TestOutputWriter(unittest.TestCase):
    """Test cases for OutputWriter functionality"""
    
    def setUp(self):
        """Set up test environment with temporary directory"""
        self.test_dir = tempfile.mkdtemp()
        self.provider = 'gmail'
        self.output_writer = OutputWriter(self.provider, self.test_dir)
    
    def tearDown(self):
        """Clean up test environment"""
        # Close any open file handles
        if hasattr(self.output_writer, 'file_handle') and self.output_writer.file_handle:
            self.output_writer.file_handle.close()
        
        # Clean up test directory
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
    
    def test_output_writer_initialization(self):
        """Test OutputWriter initialization"""
        self.assertEqual(self.output_writer.provider, 'gmail')
        self.assertEqual(self.output_writer.output_dir, self.test_dir)
        self.assertEqual(self.output_writer.email_count, 0)
        self.assertIsNone(self.output_writer.file_handle)
        
        # Test output directory is created
        self.assertTrue(os.path.exists(self.test_dir))
        
        # Test output filename format
        self.assertIsNotNone(self.output_writer.output_file)
        self.assertTrue(self.output_writer.output_file.startswith(os.path.join(self.test_dir, 'gmail-')))
        self.assertTrue(self.output_writer.output_file.endswith('.txt'))
    
    def test_output_writer_with_icloud_provider(self):
        """Test OutputWriter with iCloud provider"""
        icloud_output_writer = OutputWriter('icloud', self.test_dir)
        
        self.assertEqual(icloud_output_writer.provider, 'icloud')
        self.assertTrue(icloud_output_writer.output_file.startswith(os.path.join(self.test_dir, 'icloud-')))
    
    def test_timestamped_filename_generation(self):
        """Test that timestamped filename follows correct format"""
        # Test filename format: provider-yyyyMMdd-HHmmss.txt
        filename = os.path.basename(self.output_writer.output_file)
        
        # Should start with provider name
        self.assertTrue(filename.startswith('gmail-'))
        
        # Should end with .txt
        self.assertTrue(filename.endswith('.txt'))
        
        # Extract timestamp part
        timestamp_part = filename[len('gmail-'):-len('.txt')]
        
        # Should be in format yyyyMMdd-HHmmss
        self.assertEqual(len(timestamp_part), 15)  # yyyyMMdd-HHmmss = 15 characters
        self.assertEqual(timestamp_part[8], '-')  # Should have dash separator
        
        # Should be parseable as datetime
        try:
            parsed_datetime = datetime.datetime.strptime(timestamp_part, "%Y%m%d-%H%M%S")
            self.assertIsInstance(parsed_datetime, datetime.datetime)
        except ValueError:
            self.fail("Timestamp format is not valid")
    
    def test_create_output_file(self):
        """Test output file creation"""
        # File should not exist yet
        self.assertFalse(os.path.exists(self.output_writer.output_file))
        
        # Create output file
        self.output_writer.create_output_file()
        
        # File should now exist and be open
        self.assertTrue(os.path.exists(self.output_writer.output_file))
        self.assertIsNotNone(self.output_writer.file_handle)
        
        # Should be able to write to file
        self.assertTrue(self.output_writer.file_handle.writable())
    
    def test_write_content_basic(self):
        """Test basic content writing"""
        self.output_writer.create_output_file()
        
        test_content = "This is a test email content.\nWith multiple lines."
        
        # Write content
        self.output_writer.write_content(test_content)
        
        # Check email count
        self.assertEqual(self.output_writer.email_count, 1)
        
        # Close file to read content
        self.output_writer.finalize_output()
        
        # Read and verify content
        with open(self.output_writer.output_file, 'r', encoding='utf-8') as f:
            written_content = f.read()
        
        # Should contain delimiter and content
        self.assertIn("=== EMAIL 1 ===", written_content)
        self.assertIn(test_content, written_content)
    
    def test_write_content_with_email_number(self):
        """Test content writing with specific email number"""
        self.output_writer.create_output_file()
        
        test_content = "Test email content"
        
        # Write content with specific email number
        self.output_writer.write_content(test_content, email_number=5)
        
        # Email count should still be 0 (not incremented when number provided)
        self.assertEqual(self.output_writer.email_count, 0)
        
        # Close file to read content
        self.output_writer.finalize_output()
        
        # Read and verify content
        with open(self.output_writer.output_file, 'r', encoding='utf-8') as f:
            written_content = f.read()
        
        # Should contain specific email number
        self.assertIn("=== EMAIL 5 ===", written_content)
        self.assertIn(test_content, written_content)
    
    def test_write_multiple_emails(self):
        """Test writing multiple emails"""
        self.output_writer.create_output_file()
        
        emails = [
            "First email content",
            "Second email content",
            "Third email content"
        ]
        
        # Write multiple emails
        for email_content in emails:
            self.output_writer.write_content(email_content)
        
        # Check email count
        self.assertEqual(self.output_writer.email_count, 3)
        
        # Close file to read content
        self.output_writer.finalize_output()
        
        # Read and verify content
        with open(self.output_writer.output_file, 'r', encoding='utf-8') as f:
            written_content = f.read()
        
        # Should contain all emails with proper delimiters
        for i, email_content in enumerate(emails, 1):
            self.assertIn(f"=== EMAIL {i} ===", written_content)
            self.assertIn(email_content, written_content)
    
    def test_content_formatting(self):
        """Test proper content formatting and line breaks"""
        self.output_writer.create_output_file()
        
        # Test content without trailing newline
        content_without_newline = "Content without newline"
        self.output_writer.write_content(content_without_newline)
        
        # Test content with trailing newline
        content_with_newline = "Content with newline\n"
        self.output_writer.write_content(content_with_newline)
        
        # Close file to read content
        self.output_writer.finalize_output()
        
        # Read and verify content
        with open(self.output_writer.output_file, 'r', encoding='utf-8') as f:
            written_content = f.read()
        
        # Both should have proper line breaks and separation
        lines = written_content.split('\n')
        
        # Should have delimiters
        self.assertIn("=== EMAIL 1 ===", lines)
        self.assertIn("=== EMAIL 2 ===", lines)
        
        # Should have proper blank line separation
        email1_end_index = None
        email2_start_index = None
        
        for i, line in enumerate(lines):
            if line == content_without_newline:
                email1_end_index = i
            elif line == "=== EMAIL 2 ===":
                email2_start_index = i
        
        # There should be blank lines between emails
        self.assertIsNotNone(email1_end_index)
        self.assertIsNotNone(email2_start_index)
        self.assertTrue(email2_start_index > email1_end_index + 1)
    
    def test_finalize_output(self):
        """Test output file finalization"""
        self.output_writer.create_output_file()
        
        # Write some content
        self.output_writer.write_content("Test content")
        
        # File handle should be open
        self.assertIsNotNone(self.output_writer.file_handle)
        
        # Finalize output
        self.output_writer.finalize_output()
        
        # File handle should be closed
        self.assertIsNone(self.output_writer.file_handle)
        
        # File should still exist
        self.assertTrue(os.path.exists(self.output_writer.output_file))
    
    def test_utf8_encoding(self):
        """Test UTF-8 encoding for international characters"""
        self.output_writer.create_output_file()
        
        # Test content with international characters
        unicode_content = "Test with unicode: é, ñ, 中文, Русский, العربية"
        
        self.output_writer.write_content(unicode_content)
        self.output_writer.finalize_output()
        
        # Read back with UTF-8 encoding
        with open(self.output_writer.output_file, 'r', encoding='utf-8') as f:
            written_content = f.read()
        
        # Should contain the unicode content correctly
        self.assertIn(unicode_content, written_content)
    
    def test_error_handling_write_without_create(self):
        """Test error handling when writing without creating file"""
        test_content = "Test content"
        
        # Should raise exception when trying to write without creating file
        with self.assertRaises(Exception) as context:
            self.output_writer.write_content(test_content)
        
        self.assertIn("Output file not created", str(context.exception))
    
    def test_error_handling_directory_creation_failure(self):
        """Test error handling when directory creation fails"""
        # Try to create OutputWriter with invalid directory path
        invalid_path = "/invalid/read/only/path"
        
        with self.assertRaises(Exception) as context:
            OutputWriter('gmail', invalid_path)
        
        self.assertIn("Failed to create output directory", str(context.exception))
    
    @patch('builtins.open', side_effect=PermissionError("Permission denied"))
    def test_error_handling_file_creation_failure(self, mock_open):
        """Test error handling when file creation fails"""
        with self.assertRaises(Exception) as context:
            self.output_writer.create_output_file()
        
        self.assertIn("Failed to create output file", str(context.exception))
    
    def test_get_output_filename(self):
        """Test getting output filename"""
        filename = self.output_writer.get_output_filename()
        self.assertEqual(filename, self.output_writer.output_file)
        self.assertTrue(filename.endswith('.txt'))
    
    def test_get_email_count(self):
        """Test getting email count"""
        self.output_writer.create_output_file()
        
        # Initial count should be 0
        self.assertEqual(self.output_writer.get_email_count(), 0)
        
        # Write some emails
        for i in range(5):
            self.output_writer.write_content(f"Email {i+1}")
        
        # Count should be 5
        self.assertEqual(self.output_writer.get_email_count(), 5)
        
        self.output_writer.finalize_output()


if __name__ == '__main__':
    unittest.main() 