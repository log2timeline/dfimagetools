#!/usr/bin/env python3
"""Tests for the helper to write data streams."""

import hashlib
import os
import unittest

from dfvfs.lib import definitions as dfvfs_definitions
from dfvfs.resolver import resolver
from dfvfs.path import factory as path_spec_factory

from dfimagetools import data_stream_writer
from dfimagetools import file_entry_lister

from tests import test_lib


class DataStreamWriterTest(test_lib.BaseTestCase):
    """Tests for the data stream writer."""

    # pylint: disable=protected-access

    _FILE_DATA = b"\n".join(
        [
            b"place,user,password",
            b"bank,joesmith,superrich",
            b"alarm system,-,1234",
            b"treasure chest,-,1111",
            b"uber secret laire,admin,admin",
            b"",
        ]
    )

    def testGetDisplayPath(self):
        """Tests the GetDisplayPath function."""
        test_data_stream_writer = data_stream_writer.DataStreamWriter()

        display_path = test_data_stream_writer.GetDisplayPath(
            ["passwords.txt"], "data_stream"
        )
        self.assertEqual(display_path, "passwords.txt:data_stream")

    def testGetSanitizedPath(self):
        """Tests the GetSanitizedPath function."""
        test_data_stream_writer = data_stream_writer.DataStreamWriter()

        sanitized_path = test_data_stream_writer.GetSanitizedPath(
            ["passwords.txt"], "", ""
        )
        self.assertEqual(sanitized_path, "passwords.txt")

    def testGetSanitizedPathWithTraversalSegments(self):
        """Tests the GetSanitizedPath function with path traversal segments."""
        test_data_stream_writer = data_stream_writer.DataStreamWriter()

        sanitized_path = test_data_stream_writer.GetSanitizedPath(
            ["..", "passwords.txt"], "", "target"
        )
        self.assertEqual(sanitized_path, os.path.join("target", "_", "passwords.txt"))

        sanitized_path = test_data_stream_writer.GetSanitizedPath(
            ["etc", "..", "..", "passwd"], "", "target"
        )
        self.assertEqual(
            sanitized_path,
            os.path.join("target", "etc", "_", "_", "passwd"),
        )

        sanitized_path = test_data_stream_writer.GetSanitizedPath(
            ["passwords.txt"], "../..", "target"
        )
        self.assertEqual(
            sanitized_path,
            os.path.join("target", "passwords.txt") + "_.._..",
        )

    def testGetSanitizedPathSymlinkEscape(self):
        """Tests the GetSanitizedPath function with a symbolic link that escapes
        the target path."""
        test_data_stream_writer = data_stream_writer.DataStreamWriter()

        with test_lib.TempDirectory() as temp_directory:
            target_path = os.path.join(temp_directory, "target")
            outside_path = os.path.join(temp_directory, "outside")
            os.makedirs(target_path)
            os.makedirs(outside_path)
            os.symlink(outside_path, os.path.join(target_path, "link"))

            with self.assertRaises(ValueError):
                test_data_stream_writer.GetSanitizedPath(
                    ["link", "passwords.txt"], "", target_path
                )

    def testWriteDataStream(self):
        """Tests the WriteDataStream function."""
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

        file_entry, _ = file_entries[0]

        test_data_stream_writer = data_stream_writer.DataStreamWriter()

        with test_lib.TempDirectory() as temp_directory:
            destination_path = os.path.join(temp_directory, "passwords.txt")
            test_data_stream_writer.WriteDataStream(file_entry, "", destination_path)

            with open(destination_path, "rb") as file_object:
                file_data = file_object.read()

            self.assertEqual(file_data, self._FILE_DATA)

    def testCalculateHash(self):
        """Tests the CalculateHash function."""
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

        file_entry = resolver.Resolver.OpenFileEntry(path_spec)

        test_data_stream_writer = data_stream_writer.DataStreamWriter()
        hash_value = test_data_stream_writer.CalculateHash(file_entry, "")

        expected_hash = hashlib.sha256(self._FILE_DATA).hexdigest()
        self.assertEqual(hash_value, expected_hash)


if __name__ == "__main__":
    unittest.main()
