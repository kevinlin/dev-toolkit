#!/usr/bin/env python3
"""
Test runner for Email Exporter unit tests
"""

import unittest
import sys
import os

# Add the parent directory to the path so we can import main
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import test modules
from test_content_processor import TestContentProcessor
from test_email_processor import TestEmailProcessor, TestProcessingStats
from test_integration import TestContentProcessorEmailProcessorIntegration


def run_all_tests():
    """Run all unit tests"""
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add test cases
    suite.addTests(loader.loadTestsFromTestCase(TestContentProcessor))
    suite.addTests(loader.loadTestsFromTestCase(TestEmailProcessor))
    suite.addTests(loader.loadTestsFromTestCase(TestProcessingStats))
    suite.addTests(loader.loadTestsFromTestCase(TestContentProcessorEmailProcessorIntegration))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Return success/failure
    return result.wasSuccessful()


def run_specific_test(test_name):
    """Run a specific test class or method"""
    if test_name == 'content':
        suite = unittest.TestLoader().loadTestsFromTestCase(TestContentProcessor)
    elif test_name == 'processor':
        suite = unittest.TestLoader().loadTestsFromTestCase(TestEmailProcessor)
    elif test_name == 'stats':
        suite = unittest.TestLoader().loadTestsFromTestCase(TestProcessingStats)
    elif test_name == 'integration':
        suite = unittest.TestLoader().loadTestsFromTestCase(TestContentProcessorEmailProcessorIntegration)
    else:
        print(f"Unknown test name: {test_name}")
        print("Available tests: content, processor, stats, integration")
        return False
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return result.wasSuccessful()


if __name__ == '__main__':
    if len(sys.argv) > 1:
        # Run specific test
        test_name = sys.argv[1]
        success = run_specific_test(test_name)
    else:
        # Run all tests
        success = run_all_tests()
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)