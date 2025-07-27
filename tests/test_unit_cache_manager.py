#!/usr/bin/env python3
"""
Unit tests for CacheManager class

Tests cache operations, UID tracking, duplicate detection, and error handling.
"""

import datetime
import json
import os
import shutil

# Import the CacheManager class from email-exporter.py
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from email_exporter import CacheManager


class TestCacheManager(unittest.TestCase):
    """Test cases for CacheManager functionality"""

    def setUp(self):
        """Set up test environment with temporary directory"""
        self.test_dir = tempfile.mkdtemp()
        self.provider = "gmail"
        self.cache_manager = CacheManager(self.provider, self.test_dir)

    def tearDown(self):
        """Clean up test environment"""
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def test_cache_manager_initialization(self):
        """Test CacheManager initialization"""
        self.assertEqual(self.cache_manager.provider, "gmail")
        self.assertEqual(self.cache_manager.output_dir, self.test_dir)
        self.assertEqual(len(self.cache_manager.processed_uids), 0)

        expected_cache_file = os.path.join(self.test_dir, "gmail.cache.json")
        self.assertEqual(self.cache_manager.cache_file, expected_cache_file)

        # Test output directory is created
        self.assertTrue(os.path.exists(self.test_dir))

    def test_cache_manager_with_icloud_provider(self):
        """Test CacheManager with iCloud provider"""
        icloud_cache_manager = CacheManager("icloud", self.test_dir)

        self.assertEqual(icloud_cache_manager.provider, "icloud")
        expected_cache_file = os.path.join(self.test_dir, "icloud.cache.json")
        self.assertEqual(icloud_cache_manager.cache_file, expected_cache_file)

    def test_ensure_output_directory_creation(self):
        """Test that output directory is created if it doesn't exist"""
        new_test_dir = os.path.join(self.test_dir, "new_dir")
        self.assertFalse(os.path.exists(new_test_dir))

        CacheManager("gmail", new_test_dir)
        self.assertTrue(os.path.exists(new_test_dir))

    def test_load_cache_no_existing_file(self):
        """Test loading cache when no cache file exists"""
        self.cache_manager.load_cache()

        self.assertEqual(len(self.cache_manager.processed_uids), 0)
        self.assertIsNone(self.cache_manager.cache_metadata["last_updated"])
        self.assertEqual(self.cache_manager.cache_metadata["total_processed"], 0)

    def test_save_and_load_cache_basic(self):
        """Test basic save and load cache functionality"""
        # Add some UIDs to cache
        test_uids = ["uid1", "uid2", "uid3"]
        for uid in test_uids:
            self.cache_manager.mark_processed(uid)

        # Save cache
        self.cache_manager.save_cache()

        # Verify cache file exists
        self.assertTrue(os.path.exists(self.cache_manager.cache_file))

        # Create new cache manager and load
        new_cache_manager = CacheManager(self.provider, self.test_dir)
        new_cache_manager.load_cache()

        # Verify loaded data
        self.assertEqual(new_cache_manager.processed_uids, set(test_uids))
        self.assertIsNotNone(new_cache_manager.cache_metadata["last_updated"])
        self.assertEqual(new_cache_manager.cache_metadata["total_processed"], 3)

    def test_save_cache_file_structure(self):
        """Test that saved cache file has correct JSON structure"""
        test_uids = ["uid1", "uid2", "uid3"]
        for uid in test_uids:
            self.cache_manager.mark_processed(uid)

        self.cache_manager.save_cache()

        # Read and verify JSON structure
        with open(self.cache_manager.cache_file, encoding="utf-8") as f:
            cache_data = json.load(f)

        self.assertIn("processed_uids", cache_data)
        self.assertIn("last_updated", cache_data)
        self.assertIn("total_processed", cache_data)

        self.assertIsInstance(cache_data["processed_uids"], list)
        self.assertEqual(set(cache_data["processed_uids"]), set(test_uids))
        self.assertEqual(cache_data["total_processed"], 3)
        self.assertIsNotNone(cache_data["last_updated"])

        # Verify timestamp format
        datetime.datetime.fromisoformat(cache_data["last_updated"])

    def test_is_processed_functionality(self):
        """Test UID processing check functionality"""
        test_uid = "test_uid_123"

        # Initially should not be processed
        self.assertFalse(self.cache_manager.is_processed(test_uid))

        # Mark as processed
        self.cache_manager.mark_processed(test_uid)

        # Should now be processed
        self.assertTrue(self.cache_manager.is_processed(test_uid))

    def test_mark_processed_functionality(self):
        """Test marking UIDs as processed"""
        test_uids = ["uid1", "uid2", "uid3", "uid1"]  # Duplicate uid1

        for uid in test_uids:
            self.cache_manager.mark_processed(uid)

        # Should contain unique UIDs only
        self.assertEqual(len(self.cache_manager.processed_uids), 3)
        self.assertEqual(self.cache_manager.processed_uids, {"uid1", "uid2", "uid3"})

    def test_cache_stats(self):
        """Test cache statistics functionality"""
        # Add some UIDs
        uids = ["uid1", "uid2", "uid3"]
        for uid in uids:
            self.cache_manager.mark_processed(uid)

        stats = self.cache_manager.get_cache_stats()

        self.assertEqual(stats["total_cached_uids"], 3)
        self.assertEqual(stats["provider"], "gmail")
        self.assertIn("cache_file", stats)
        self.assertIn("last_updated", stats)

    def test_content_hash_operations(self):
        """Test content hash addition and checking"""
        hash1 = "abc123def456"
        hash2 = "xyz789uvw012"

        # Initially no content hashes
        self.assertFalse(self.cache_manager.is_content_duplicate(hash1))
        self.assertEqual(len(self.cache_manager.get_content_hashes()), 0)

        # Add content hashes
        self.cache_manager.add_content_hash(hash1)
        self.cache_manager.add_content_hash(hash2)

        # Check they're detected as duplicates
        self.assertTrue(self.cache_manager.is_content_duplicate(hash1))
        self.assertTrue(self.cache_manager.is_content_duplicate(hash2))
        self.assertFalse(self.cache_manager.is_content_duplicate("nonexistent"))

        # Check content hashes set
        hashes = self.cache_manager.get_content_hashes()
        self.assertEqual(len(hashes), 2)
        self.assertIn(hash1, hashes)
        self.assertIn(hash2, hashes)

    def test_content_hash_empty_handling(self):
        """Test handling of empty content hashes"""
        # Empty hashes should not be added
        self.cache_manager.add_content_hash("")
        self.cache_manager.add_content_hash(None)

        self.assertEqual(len(self.cache_manager.get_content_hashes()), 0)
        self.assertFalse(self.cache_manager.is_content_duplicate(""))

    def test_content_hash_duplicate_addition(self):
        """Test that adding the same content hash multiple times doesn't create duplicates"""
        hash1 = "abc123def456"

        # Add same hash multiple times
        self.cache_manager.add_content_hash(hash1)
        self.cache_manager.add_content_hash(hash1)
        self.cache_manager.add_content_hash(hash1)

        # Should only have one instance
        hashes = self.cache_manager.get_content_hashes()
        self.assertEqual(len(hashes), 1)
        self.assertIn(hash1, hashes)

    def test_cache_save_and_load_with_content_hashes(self):
        """Test saving and loading cache with content hashes"""
        # Add UIDs and content hashes
        uids = ["uid1", "uid2"]
        hashes = ["hash1", "hash2", "hash3"]

        for uid in uids:
            self.cache_manager.mark_processed(uid)
        for hash_val in hashes:
            self.cache_manager.add_content_hash(hash_val)

        # Save cache
        self.cache_manager.save_cache()

        # Create new cache manager to test loading
        new_cache_manager = CacheManager("gmail", self.test_dir)
        new_cache_manager.load_cache()

        # Verify UIDs and content hashes were loaded
        self.assertEqual(new_cache_manager.processed_uids, set(uids))
        self.assertEqual(new_cache_manager.get_content_hashes(), set(hashes))

        # Verify all hashes are detected as duplicates
        for hash_val in hashes:
            self.assertTrue(new_cache_manager.is_content_duplicate(hash_val))

    def test_cache_stats_with_content_hashes(self):
        """Test cache statistics with content hashes"""
        # Add UIDs and content hashes
        uids = ["uid1", "uid2", "uid3"]
        hashes = ["hash1", "hash2"]

        for uid in uids:
            self.cache_manager.mark_processed(uid)
        for hash_val in hashes:
            self.cache_manager.add_content_hash(hash_val)

        stats = self.cache_manager.get_cache_stats()

        self.assertEqual(stats["total_cached_uids"], 3)
        self.assertEqual(stats["total_cached_content_hashes"], 2)
        self.assertEqual(stats["provider"], "gmail")

    def test_content_hash_isolation(self):
        """Test that get_content_hashes returns a copy, not the original set"""
        hash1 = "abc123"
        self.cache_manager.add_content_hash(hash1)

        # Get content hashes and modify the returned set
        hashes = self.cache_manager.get_content_hashes()
        hashes.add("should_not_affect_cache")

        # Original cache should be unaffected
        original_hashes = self.cache_manager.get_content_hashes()
        self.assertEqual(len(original_hashes), 1)
        self.assertIn(hash1, original_hashes)
        self.assertNotIn("should_not_affect_cache", original_hashes)

    def test_cache_corruption_recovery_with_content_hashes(self):
        """Test cache recovery when file is corrupted, including content hashes"""
        # Create corrupted cache file
        with open(self.cache_manager.cache_file, "w") as f:
            f.write("invalid json content")

        # Loading should recover gracefully
        self.cache_manager.load_cache()

        # Should start with empty cache
        self.assertEqual(len(self.cache_manager.processed_uids), 0)
        self.assertEqual(len(self.cache_manager.get_content_hashes()), 0)

        # Should be able to add new data
        self.cache_manager.mark_processed("test_uid")
        self.cache_manager.add_content_hash("test_hash")

        self.assertTrue(self.cache_manager.is_processed("test_uid"))
        self.assertTrue(self.cache_manager.is_content_duplicate("test_hash"))

    def test_load_corrupted_cache_file(self):
        """Test handling of corrupted cache file"""
        # Create corrupted cache file
        with open(self.cache_manager.cache_file, "w") as f:
            f.write("invalid json content")

        # Should handle corruption gracefully
        self.cache_manager.load_cache()

        # Should start with empty cache
        self.assertEqual(len(self.cache_manager.processed_uids), 0)
        self.assertEqual(self.cache_manager.cache_metadata["total_processed"], 0)

    def test_load_cache_invalid_structure(self):
        """Test handling of cache file with invalid structure"""
        # Create cache file with invalid structure
        invalid_data = ["not", "a", "dict"]
        with open(self.cache_manager.cache_file, "w") as f:
            json.dump(invalid_data, f)

        # Should handle invalid structure gracefully
        self.cache_manager.load_cache()

        # Should start with empty cache
        self.assertEqual(len(self.cache_manager.processed_uids), 0)

    def test_load_cache_invalid_uids_type(self):
        """Test handling of cache file with invalid UIDs type"""
        # Create cache file with invalid UIDs type
        invalid_data = {
            "processed_uids": "not_a_list",
            "last_updated": "2024-01-01T00:00:00",
            "total_processed": 1,
        }
        with open(self.cache_manager.cache_file, "w") as f:
            json.dump(invalid_data, f)

        # Should handle invalid UIDs type gracefully
        self.cache_manager.load_cache()

        # Should start with empty cache
        self.assertEqual(len(self.cache_manager.processed_uids), 0)

    def test_cache_backup_on_save(self):
        """Test that cache creates backup when overwriting existing file"""
        # Create initial cache
        self.cache_manager.mark_processed("uid1")
        self.cache_manager.save_cache()

        # Add more data and save again
        self.cache_manager.mark_processed("uid2")
        self.cache_manager.save_cache()

        # Check that backup file exists
        backup_file = self.cache_manager.cache_file + ".bak"
        self.assertTrue(os.path.exists(backup_file))

        # Verify backup contains original data
        with open(backup_file, encoding="utf-8") as f:
            backup_data = json.load(f)

        self.assertEqual(backup_data["processed_uids"], ["uid1"])
        self.assertEqual(backup_data["total_processed"], 1)

    def test_atomic_save_operation(self):
        """Test that save operation is atomic (uses temp file)"""
        self.cache_manager.mark_processed("uid1")

        # Mock file operations to simulate interruption
        original_rename = os.rename
        call_count = 0

        def mock_rename(src, dst):
            nonlocal call_count
            call_count += 1
            if call_count == 1 and "tmp" in src:
                # Simulate interruption during atomic operation
                raise OSError("Simulated interruption")
            return original_rename(src, dst)

        with patch("os.rename", side_effect=mock_rename), self.assertRaises(OSError):
            self.cache_manager.save_cache()

        # Verify temp file is cleaned up
        temp_file = self.cache_manager.cache_file + ".tmp"
        self.assertFalse(os.path.exists(temp_file))

    def test_save_cache_with_unicode_content(self):
        """Test saving cache with Unicode UIDs"""
        unicode_uids = ["uid_测试", "uid_ñoño", "uid_emoji_😀"]

        for uid in unicode_uids:
            self.cache_manager.mark_processed(uid)

        self.cache_manager.save_cache()

        # Load and verify Unicode handling
        new_cache_manager = CacheManager(self.provider, self.test_dir)
        new_cache_manager.load_cache()

        self.assertEqual(new_cache_manager.processed_uids, set(unicode_uids))

    def test_large_cache_performance(self):
        """Test cache performance with large number of UIDs"""
        import time

        # Add large number of UIDs
        large_uid_count = 10000
        start_time = time.time()

        for i in range(large_uid_count):
            self.cache_manager.mark_processed(f"uid_{i:06d}")

        add_time = time.time() - start_time

        # Save cache
        start_time = time.time()
        self.cache_manager.save_cache()
        save_time = time.time() - start_time

        # Load cache
        new_cache_manager = CacheManager(self.provider, self.test_dir)
        start_time = time.time()
        new_cache_manager.load_cache()
        load_time = time.time() - start_time

        # Verify correctness
        self.assertEqual(len(new_cache_manager.processed_uids), large_uid_count)

        # Performance assertions (generous limits for CI environments)
        self.assertLess(add_time, 5.0, "Adding UIDs took too long")
        self.assertLess(save_time, 10.0, "Saving cache took too long")
        self.assertLess(load_time, 10.0, "Loading cache took too long")

    def test_cache_sorted_uids_consistency(self):
        """Test that cache saves UIDs in sorted order for consistency"""
        unsorted_uids = ["uid_c", "uid_a", "uid_b", "uid_10", "uid_2"]

        for uid in unsorted_uids:
            self.cache_manager.mark_processed(uid)

        self.cache_manager.save_cache()

        # Read cache file directly
        with open(self.cache_manager.cache_file, encoding="utf-8") as f:
            cache_data = json.load(f)

        # Verify UIDs are sorted
        expected_sorted = sorted(unsorted_uids)
        self.assertEqual(cache_data["processed_uids"], expected_sorted)


if __name__ == "__main__":
    unittest.main()
