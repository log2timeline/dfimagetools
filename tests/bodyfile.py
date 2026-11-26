#!/usr/bin/env python3
"""Tests for the helper to generating bodyfile entries."""

import unittest

from dfvfs.lib import definitions as dfvfs_definitions
from dfvfs.resolver import resolver
from dfvfs.path import factory as path_spec_factory

from dfimagetools import bodyfile
from dfimagetools import file_entry_lister

from tests import test_lib


class BodyfileGeneratorTest(test_lib.BaseTestCase):
    """Tests for the bodyfile generator."""

    # pylint: disable=protected-access

    def testEscapeStringWithEscapeCharacters(self):
        """Tests the _EscapeString function with all escape characters."""
        test_object = bodyfile.BodyfileGenerator()

        for character in test_object._escape_characters:
            string = f"a{chr(character):s}b"
            expected_string = string.translate(test_object._escape_characters)
            self.assertNotEqual(expected_string, string)

            escaped_string = test_object._EscapeString(string)
            self.assertEqual(escaped_string, expected_string)

    def testEscapeString(self):
        """Tests the _EscapeString function."""
        test_object = bodyfile.BodyfileGenerator()

        # Printable characters.
        self.assertEqual(test_object._EscapeString(""), "")
        self.assertEqual(test_object._EscapeString("file.txt"), "file.txt")
        self.assertEqual(test_object._EscapeString("Program Files"), "Program Files")
        self.assertEqual(test_object._EscapeString("\u00fcber"), "\u00fcber")

        # Printable characters that are escaped.
        self.assertEqual(test_object._EscapeString("a/b"), "a\\/b")
        self.assertEqual(test_object._EscapeString("a:b"), "a\\:b")
        self.assertEqual(test_object._EscapeString("a\\b"), "a\\\\b")
        self.assertEqual(test_object._EscapeString("a|b"), "a\\|b")

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

    def testGetModeString(self):
        """Tests the _GetModeString function."""
        test_bodyfile_generator = bodyfile.BodyfileGenerator()

        mode_string = test_bodyfile_generator._GetModeString(0)
        self.assertEqual(mode_string, "----------")

        mode_string = test_bodyfile_generator._GetModeString(0o777)
        self.assertEqual(mode_string, "-rwxrwxrwx")

        mode_string = test_bodyfile_generator._GetModeString(0x1000)
        self.assertEqual(mode_string, "p---------")

        mode_string = test_bodyfile_generator._GetModeString(0x2000)
        self.assertEqual(mode_string, "c---------")

        mode_string = test_bodyfile_generator._GetModeString(0x4000)
        self.assertEqual(mode_string, "d---------")

        mode_string = test_bodyfile_generator._GetModeString(0x6000)
        self.assertEqual(mode_string, "b---------")

        mode_string = test_bodyfile_generator._GetModeString(0xA000)
        self.assertEqual(mode_string, "l---------")

        mode_string = test_bodyfile_generator._GetModeString(0xC000)
        self.assertEqual(mode_string, "s---------")

    def testGetEntries(self):
        """Tests the GetEntries function."""
        path = self._GetTestFilePath(["image.qcow2"])
        self._SkipIfPathNotExists(path)

        path_spec = path_spec_factory.Factory.NewPathSpec(
            dfvfs_definitions.TYPE_INDICATOR_OS, location=path
        )
        path_spec = path_spec_factory.Factory.NewPathSpec(
            dfvfs_definitions.TYPE_INDICATOR_QCOW, parent=path_spec
        )
        path_spec = path_spec_factory.Factory.NewPathSpec(
            dfvfs_definitions.TYPE_INDICATOR_TSK,
            location="/passwords.txt",
            parent=path_spec,
        )
        file_system = resolver.Resolver.OpenFileSystem(path_spec)
        file_entry = resolver.Resolver.OpenFileEntry(path_spec)

        test_lister = file_entry_lister.FileEntryLister()
        file_entries = list(test_lister._ListFileEntry(file_system, file_entry, [""]))

        self.assertEqual(len(file_entries), 1)

        test_bodyfile_generator = bodyfile.BodyfileGenerator()

        expected_bodyfile_entry = (
            "N/A (skipped)|/passwords.txt|15|-r--------|151107|5000|116|1337961653|"
            "1337961653|1337961663|"
        )
        bodyfile_entries = list(test_bodyfile_generator.GetEntries(*file_entries[0]))
        self.assertEqual(len(bodyfile_entries), 1)
        self.assertEqual(bodyfile_entries[0], expected_bodyfile_entry)

        test_bodyfile_generator = bodyfile.BodyfileGenerator(use_original_md5=True)

        expected_bodyfile_entry = (
            "0|/passwords.txt|15|-r--------|151107|5000|116|1337961653|"
            "1337961653|1337961663|"
        )
        bodyfile_entries = list(test_bodyfile_generator.GetEntries(*file_entries[0]))
        self.assertEqual(len(bodyfile_entries), 1)
        self.assertEqual(bodyfile_entries[0], expected_bodyfile_entry)

    def testGetEntriesWithNTFSImage(self):
        """Tests the GetEntries function with a NTFS image."""
        path = self._GetTestFilePath(["ntfs.vhd"])
        self._SkipIfPathNotExists(path)

        bodyfile_path = self._GetTestFilePath(["ntfs.vhd.bodyfile"])
        self._SkipIfPathNotExists(bodyfile_path)

        test_lister = file_entry_lister.FileEntryLister()
        base_path_specs = test_lister.GetBasePathSpecs(path)
        file_entries = list(test_lister.ListFileEntries(base_path_specs))

        self.assertEqual(len(file_entries), 40)

        test_bodyfile_generator = bodyfile.BodyfileGenerator(use_original_md5=True)

        bodyfile_entries = []
        for file_entry, path_segments in file_entries:
            for bodyfile_entry in test_bodyfile_generator.GetEntries(
                file_entry, path_segments
            ):
                bodyfile_entries.append(bodyfile_entry)

        self.assertEqual(len(bodyfile_entries), 89)

        with open(bodyfile_path, "r", encoding="utf-8") as file_object:
            expected_bodyfile_entries = [
                entry for entry in file_object.read().split("\n") if entry
            ]

        self.assertEqual(len(bodyfile_entries), len(expected_bodyfile_entries))
        self.assertEqual(bodyfile_entries, expected_bodyfile_entries)


if __name__ == "__main__":
    unittest.main()
