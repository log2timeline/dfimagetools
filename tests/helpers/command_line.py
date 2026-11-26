#!/usr/bin/env python3
"""Tests for the command line helper functions."""

import argparse
import unittest

from dfimagetools.helpers import command_line

from tests import test_lib


class ParseStorageMediaImageCLIArgumentsTest(test_lib.BaseTestCase):
    """Tests for the ParseStorageMediaImageCLIArguments function."""

    def testParseStorageMediaImageCLIArgumentsKeyData(self):
        """Tests the ParseStorageMediaImageCLIArguments function with key data."""
        options = argparse.Namespace(credentials=["key_data:00ff"])

        _, volume_scanner_options = command_line.ParseStorageMediaImageCLIArguments(
            options
        )
        self.assertEqual(
            volume_scanner_options.credentials, [("key_data", b"\x00\xff")]
        )

    def testParseStorageMediaImageCLIArgumentsInvalidKeyData(self):
        """Tests the ParseStorageMediaImageCLIArguments function with invalid data."""
        # Key data with non-hexadecimal digits.
        options = argparse.Namespace(credentials=["key_data:zz"])

        with self.assertRaises(RuntimeError):
            command_line.ParseStorageMediaImageCLIArguments(options)

        # Key data with an odd number of hexadecimal digits.
        options = argparse.Namespace(credentials=["key_data:abc"])

        with self.assertRaises(RuntimeError):
            command_line.ParseStorageMediaImageCLIArguments(options)


if __name__ == "__main__":
    unittest.main()
