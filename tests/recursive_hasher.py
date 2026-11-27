#!/usr/bin/env python3
"""Tests for the helper to recursively calculate a message digest hash."""

import unittest

from dfimagetools import recursive_hasher

from tests import test_lib


class RecursiveHasherTest(test_lib.BaseTestCase):
    """Tests for the recursive hasher."""

    # pylint: disable=protected-access

    def testEscapeStringWithEscapeCharacters(self):
        """Tests the _EscapeString function with all escape characters."""
        test_object = recursive_hasher.RecursiveHasher()

        for character in test_object._escape_characters:
            string = f"a{chr(character):s}b"
            expected_string = string.translate(test_object._escape_characters)
            self.assertNotEqual(expected_string, string)

            escaped_string = test_object._EscapeString(string)
            self.assertEqual(escaped_string, expected_string)

    def testEscapeString(self):
        """Tests the _EscapeString function."""
        test_object = recursive_hasher.RecursiveHasher()

        # Printable characters.
        self.assertEqual(test_object._EscapeString(""), "")
        self.assertEqual(test_object._EscapeString("file.txt"), "file.txt")
        self.assertEqual(test_object._EscapeString("Program Files"), "Program Files")
        self.assertEqual(test_object._EscapeString("\u00fcber"), "\u00fcber")

        # Printable characters that are escaped.
        self.assertEqual(test_object._EscapeString("a/b"), "a\\/b")
        self.assertEqual(test_object._EscapeString("a:b"), "a\\:b")
        self.assertEqual(test_object._EscapeString("a\\b"), "a\\\\b")
        self.assertEqual(test_object._EscapeString("a|b"), "a|b")

        # C0 and C1 control characters.
        self.assertEqual(test_object._EscapeString("a\tb"), "a\\x09b")
        self.assertEqual(test_object._EscapeString("a\x85b"), "a\\x85b")

        # Unicode surrogate characters.
        self.assertEqual(test_object._EscapeString("a\ud800b"), "a\\U0000d800b")

        # Undefined Unicode characters.
        self.assertEqual(test_object._EscapeString("a\ufffeb"), "a\\U0000fffeb")

        # Observed non-printable Unicode characters.
        self.assertEqual(test_object._EscapeString("a\u2028b"), "a\\U00002028b")

        # Non-printable characters that are not escaped.
        self.assertEqual(test_object._EscapeString("a\u00adb"), "a\u00adb")

        # Mixed printable and non-printable characters.
        self.assertEqual(test_object._EscapeString("a/\tb"), "a\\/\\x09b")

    def testGetDisplayPath(self):
        """Tests the _GetDisplayPath function."""
        test_hasher = recursive_hasher.RecursiveHasher()

        display_path = test_hasher._GetDisplayPath([""], None)
        self.assertEqual(display_path, "/")

        display_path = test_hasher._GetDisplayPath(["", "a_directory", "a_file"], None)
        self.assertEqual(display_path, "/a_directory/a_file")

        display_path = test_hasher._GetDisplayPath(["", "a:b", "c\td"], "e/f")
        self.assertEqual(display_path, "/a\\:b/c\\x09d:e\\/f")


if __name__ == "__main__":
    unittest.main()
