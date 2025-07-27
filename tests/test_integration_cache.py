#!/usr/bin/env python3
"""
Integration tests for CacheManager with EmailProcessor

Tests cache integration, duplicate detection during email processing,
and end-to-end caching workflow.
"""

import email.message
import os
import shutil

# Import classes from email-exporter.py
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from email_exporter import CacheManager, EmailProcessor, ProcessingStats


class TestCacheIntegration(unittest.TestCase):
    """Test cases for CacheManager integration with EmailProcessor"""

    def setUp(self):
        """Set up test environment"""
        self.test_dir = tempfile.mkdtemp()
        self.provider = "gmail"
        self.cache_manager = CacheManager(self.provider, self.test_dir)

        # Create mock IMAP manager
        self.mock_imap_manager = Mock()
        self.mock_imap_manager.fetch_message_uids.return_value = []

        # Create email processor with cache manager
        self.email_processor = EmailProcessor(self.mock_imap_manager, self.cache_manager)

    def tearDown(self):
        """Clean up test environment"""
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def _create_mock_email_message(
        self,
        uid: str,
        subject: str = "Test Subject",
        body: str = "This is a test email with more than twenty words to pass validation. It contains meaningful content for testing purposes.",
    ):
        """Create a mock email message for testing"""
        msg = email.message.EmailMessage()
        msg["Subject"] = subject
        msg["Date"] = "Mon, 01 Jan 2024 12:00:00 +0000"
        msg["From"] = "test@example.com"
        msg["To"] = "recipient@example.com"
        msg.set_content(body)
        return msg

    def test_cache_integration_with_email_processor(self):
        """Test that EmailProcessor correctly integrates with CacheManager"""
        # Verify cache manager is properly set
        self.assertIsNotNone(self.email_processor.cache_manager)
        self.assertEqual(self.email_processor.cache_manager.provider, "gmail")

    def test_email_processor_without_cache_manager(self):
        """Test EmailProcessor works without cache manager"""
        processor_no_cache = EmailProcessor(self.mock_imap_manager)
        self.assertIsNone(processor_no_cache.cache_manager)

        # Should still process emails normally
        stats = processor_no_cache.process_emails()
        self.assertIsInstance(stats, ProcessingStats)

    def test_cache_loading_during_email_processing(self):
        """Test that cache is loaded when email processing starts"""
        # Pre-populate cache
        test_uids = ["uid1", "uid2", "uid3"]
        for uid in test_uids:
            self.cache_manager.mark_processed(uid)
        self.cache_manager.save_cache()

        # Create new processor with fresh cache manager
        new_cache_manager = CacheManager(self.provider, self.test_dir)
        new_processor = EmailProcessor(self.mock_imap_manager, new_cache_manager)

        # Mock empty UID batch
        self.mock_imap_manager.fetch_message_uids.return_value = [[]]

        # Process emails - this should load the cache
        with patch("builtins.print") as mock_print:
            new_processor.process_emails()

        # Verify cache was loaded
        self.assertEqual(len(new_cache_manager.processed_uids), 3)

        # Verify cache loading was logged
        print_calls = [str(call) for call in mock_print.call_args_list]
        self.assertTrue(
            any("Cache loaded: 3 previously processed UIDs" in call for call in print_calls)
        )

    def test_duplicate_detection_during_processing(self):
        """Test that cached UIDs are detected as duplicates during processing"""
        # Pre-populate cache with some UIDs and save to disk
        cached_uids = ["uid1", "uid2"]
        for uid in cached_uids:
            self.cache_manager.mark_processed(uid)
        self.cache_manager.save_cache()  # Save to disk so load_cache() works

        # Set up batch with mix of cached and new UIDs
        test_batch = ["uid1", "uid2", "uid3", "uid4"]  # uid1, uid2 are cached
        self.mock_imap_manager.fetch_message_uids.return_value = [test_batch]

        # Mock fetch_message to return valid messages for new UIDs only
        # Create different content for each message to avoid content-based duplicates
        def mock_fetch_message(uid):
            if uid in cached_uids:
                self.fail(f"Should not fetch cached UID: {uid}")
            elif uid == "uid3":
                return self._create_mock_email_message(
                    uid,
                    "Subject 3",
                    "This is unique content for uid3 with more than twenty words to pass validation. It contains meaningful content for testing purposes and should not be detected as duplicate.",
                )
            elif uid == "uid4":
                return self._create_mock_email_message(
                    uid,
                    "Subject 4",
                    "This is different unique content for uid4 with more than twenty words to pass validation. It contains different meaningful content for testing purposes and should not be detected as duplicate.",
                )
            return self._create_mock_email_message(uid)

        self.mock_imap_manager.fetch_message.side_effect = mock_fetch_message

        # Process emails
        stats = self.email_processor.process_emails()

        # Verify duplicate detection
        self.assertEqual(stats.skipped_duplicate, 2)  # uid1, uid2 were cached
        self.assertEqual(
            self.mock_imap_manager.fetch_message.call_count, 2
        )  # Only uid3, uid4 fetched

    def test_cache_saving_after_processing(self):
        """Test that cache is saved after email processing completes"""
        # Set up batch with new UIDs
        test_batch = ["uid1", "uid2", "uid3"]
        self.mock_imap_manager.fetch_message_uids.return_value = [test_batch]

        # Mock fetch_message to return valid messages with unique content
        def mock_fetch_message(uid):
            if uid == "uid1":
                return self._create_mock_email_message(
                    uid,
                    "Subject 1",
                    "This is unique content for uid1 with more than twenty words to pass validation. It contains meaningful content for testing purposes and should not be detected as duplicate.",
                )
            elif uid == "uid2":
                return self._create_mock_email_message(
                    uid,
                    "Subject 2",
                    "This is different unique content for uid2 with more than twenty words to pass validation. It contains different meaningful content for testing purposes and should not be detected as duplicate.",
                )
            elif uid == "uid3":
                return self._create_mock_email_message(
                    uid,
                    "Subject 3",
                    "This is another unique content for uid3 with more than twenty words to pass validation. It contains another different meaningful content for testing purposes and should not be detected as duplicate.",
                )
            return self._create_mock_email_message(uid)

        self.mock_imap_manager.fetch_message.side_effect = mock_fetch_message

        # Verify cache file doesn't exist initially
        self.assertFalse(os.path.exists(self.cache_manager.cache_file))

        # Process emails
        with patch("builtins.print") as mock_print:
            self.email_processor.process_emails()

        # Verify cache file was created and saved
        self.assertTrue(os.path.exists(self.cache_manager.cache_file))

        # Verify cache saving was logged
        print_calls = [str(call) for call in mock_print.call_args_list]
        self.assertTrue(any("Cache updated and saved successfully" in call for call in print_calls))

        # Verify all UIDs were cached
        self.assertEqual(len(self.cache_manager.processed_uids), 3)
        for uid in test_batch:
            self.assertTrue(self.cache_manager.is_processed(uid))

    def test_cache_saving_on_error(self):
        """Test that cache is saved even when processing encounters errors"""
        test_batch = ["uid1", "uid2"]
        self.mock_imap_manager.fetch_message_uids.return_value = [test_batch]

        # Mock fetch_message to succeed for first UID, then raise exception
        def mock_fetch_message(uid):
            if uid == "uid1":
                return self._create_mock_email_message(uid)
            else:
                raise Exception("Simulated fetch error")

        self.mock_imap_manager.fetch_message.side_effect = mock_fetch_message

        # Process emails - should handle error gracefully
        with patch("builtins.print"):
            stats = self.email_processor.process_emails()

        # Verify that uid1 was cached despite error with uid2
        self.assertTrue(self.cache_manager.is_processed("uid1"))
        self.assertTrue(os.path.exists(self.cache_manager.cache_file))

        # Verify error was recorded
        self.assertEqual(stats.errors, 1)

    def test_cache_persistence_across_multiple_runs(self):
        """Test that cache persists across multiple processing runs"""
        # First run - process some UIDs with unique content
        first_batch = ["uid1", "uid2"]
        self.mock_imap_manager.fetch_message_uids.return_value = [first_batch]

        def first_mock_fetch_message(uid):
            if uid == "uid1":
                return self._create_mock_email_message(
                    uid,
                    "Subject 1",
                    "This is unique content for uid1 first run with more than twenty words to pass validation. It contains meaningful content for testing purposes and should not be detected as duplicate.",
                )
            elif uid == "uid2":
                return self._create_mock_email_message(
                    uid,
                    "Subject 2",
                    "This is different unique content for uid2 first run with more than twenty words to pass validation. It contains different meaningful content for testing purposes.",
                )
            return self._create_mock_email_message(uid)

        self.mock_imap_manager.fetch_message.side_effect = first_mock_fetch_message

        self.email_processor.process_emails()

        # Verify first batch was processed and cached
        self.assertEqual(len(self.cache_manager.processed_uids), 2)

        # Second run - create new processor to simulate new execution
        new_cache_manager = CacheManager(self.provider, self.test_dir)
        new_processor = EmailProcessor(self.mock_imap_manager, new_cache_manager)

        # Second batch includes some previously processed UIDs
        second_batch = ["uid2", "uid3", "uid4"]  # uid2 was processed before
        self.mock_imap_manager.fetch_message_uids.return_value = [second_batch]

        # Reset mock call count and set up unique content for new UIDs
        self.mock_imap_manager.fetch_message.reset_mock()

        def second_mock_fetch_message(uid):
            if uid == "uid2":
                self.fail(f"Should not fetch cached UID: {uid}")
            elif uid == "uid3":
                return self._create_mock_email_message(
                    uid,
                    "Subject 3",
                    "This is unique content for uid3 second run with more than twenty words to pass validation. It contains meaningful content for testing purposes and should not be detected as duplicate.",
                )
            elif uid == "uid4":
                return self._create_mock_email_message(
                    uid,
                    "Subject 4",
                    "This is different unique content for uid4 second run with more than twenty words to pass validation. It contains different meaningful content for testing purposes.",
                )
            return self._create_mock_email_message(uid)

        self.mock_imap_manager.fetch_message.side_effect = second_mock_fetch_message

        second_stats = new_processor.process_emails()

        # Verify that uid2 was skipped as duplicate
        self.assertEqual(second_stats.skipped_duplicate, 1)

        # Verify only uid3 and uid4 were fetched (uid2 was cached)
        self.assertEqual(self.mock_imap_manager.fetch_message.call_count, 2)

        # Verify final cache contains all UIDs
        final_cache_manager = CacheManager(self.provider, self.test_dir)
        final_cache_manager.load_cache()
        expected_uids = {"uid1", "uid2", "uid3", "uid4"}
        self.assertEqual(final_cache_manager.processed_uids, expected_uids)

    def test_cache_with_system_generated_messages(self):
        """Test that system-generated messages are not cached"""
        test_batch = ["uid1", "uid2"]
        self.mock_imap_manager.fetch_message_uids.return_value = [test_batch]

        # Create one normal message and one system-generated message
        def mock_fetch_message(uid):
            if uid == "uid1":
                return self._create_mock_email_message(uid, "Normal message")
            else:
                # Create system-generated message
                msg = self._create_mock_email_message(uid, "Auto-Reply: Out of Office")
                msg["Auto-Submitted"] = "auto-replied"
                return msg

        self.mock_imap_manager.fetch_message.side_effect = mock_fetch_message

        stats = self.email_processor.process_emails()

        # Verify that only the normal message was cached
        self.assertEqual(len(self.cache_manager.processed_uids), 1)
        self.assertTrue(self.cache_manager.is_processed("uid1"))
        self.assertFalse(self.cache_manager.is_processed("uid2"))  # System message not cached

        # Verify statistics
        self.assertEqual(stats.skipped_system, 1)
        self.assertEqual(stats.retained, 1)

    def test_cache_with_short_messages(self):
        """Test that messages failing validation are not cached"""
        test_batch = ["uid1", "uid2"]
        self.mock_imap_manager.fetch_message_uids.return_value = [test_batch]

        def mock_fetch_message(uid):
            if uid == "uid1":
                return self._create_mock_email_message(
                    uid,
                    "Normal message",
                    "This is a long enough message with more than twenty words to pass the validation check properly and test caching.",
                )
            else:
                # Short message that will fail validation
                return self._create_mock_email_message(uid, "Short message", "Too short.")

        self.mock_imap_manager.fetch_message.side_effect = mock_fetch_message

        stats = self.email_processor.process_emails()

        # Verify that only the valid message was cached
        self.assertEqual(len(self.cache_manager.processed_uids), 1)
        self.assertTrue(self.cache_manager.is_processed("uid1"))
        self.assertFalse(self.cache_manager.is_processed("uid2"))  # Short message not cached

        # Verify statistics
        self.assertEqual(stats.skipped_short, 1)
        self.assertEqual(stats.retained, 1)

    def test_cache_manager_error_handling_in_processor(self):
        """Test EmailProcessor handles cache manager errors gracefully"""
        test_batch = ["uid1"]
        self.mock_imap_manager.fetch_message_uids.return_value = [test_batch]
        self.mock_imap_manager.fetch_message.side_effect = (
            lambda uid: self._create_mock_email_message(uid)
        )

        # Mock cache save to raise an exception
        with patch.object(
            self.cache_manager, "save_cache", side_effect=Exception("Cache save error")
        ):
            with patch("builtins.print") as mock_print:
                stats = self.email_processor.process_emails()

        # Verify processing completed despite cache error
        self.assertEqual(stats.retained, 1)

        # Verify cache error was logged
        print_calls = [str(call) for call in mock_print.call_args_list]
        self.assertTrue(any("Warning: Failed to save cache" in call for call in print_calls))

    def test_large_batch_caching_performance(self):
        """Test cache performance with large batches"""
        import time

        # Create large batch
        large_batch = [f"uid_{i:05d}" for i in range(1000)]
        self.mock_imap_manager.fetch_message_uids.return_value = [large_batch]

        # Create unique content for each message to avoid content-based duplicates
        def mock_fetch_message(uid):
            uid_num = uid.split("_")[1]
            return self._create_mock_email_message(
                uid,
                f"Subject {uid_num}",
                f"This is unique content for {uid} with more than twenty words to pass validation. It contains meaningful content for testing purposes and should not be detected as duplicate. Message number {uid_num}.",
            )

        self.mock_imap_manager.fetch_message.side_effect = mock_fetch_message

        start_time = time.time()
        stats = self.email_processor.process_emails()
        processing_time = time.time() - start_time

        # Verify all messages were processed and cached
        self.assertEqual(stats.retained, 1000)
        self.assertEqual(len(self.cache_manager.processed_uids), 1000)

        # Performance check (generous limit for CI)
        self.assertLess(processing_time, 30.0, "Large batch processing took too long")

        # Verify cache file exists and is valid
        self.assertTrue(os.path.exists(self.cache_manager.cache_file))


if __name__ == "__main__":
    unittest.main()
