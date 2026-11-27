#!/usr/bin/env python3
"""Tests for the helper to write data streams."""

import hashlib
import io
import os
import unittest

from dfvfs.lib import definitions as dfvfs_definitions
from dfvfs.resolver import resolver
from dfvfs.path import factory as path_spec_factory

from dfimagetools import data_stream_writer
from dfimagetools import file_entry_lister

from tests import test_lib


class _FakeFileEntry:
    """Fake file entry that returns a predefined file-like object."""

    def __init__(self, file_object):
        """Initializes a fake file entry.

        Args:
          file_object (io.BytesIO): file-like object or None.
        """
        super().__init__()
        self._file_object = file_object

    def GetFileObject(self, data_stream_name=""):
        """Retrieves a file-like object of a data stream.

        Args:
          data_stream_name (Optional[str]): name of the data stream, unused.

        Returns:
          io.BytesIO: file-like object or None.
        """
        # pylint: disable=unused-argument
        return self._file_object


class _SmallBufferDataStreamWriter(data_stream_writer.DataStreamWriter):
    """Data stream writer with a small read buffer."""

    _READ_BUFFER_SIZE = 16


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

    def _GetPasswordsFileEntry(self):
        """Retrieves the passwords.txt file entry from image.qcow2.

        Returns:
          dfvfs.FileEntry: file entry.
        """
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
        return resolver.Resolver.OpenFileEntry(path_spec)

    def testCalculateHashAndReadData(self):
        """Tests the CalculateHashAndReadData function."""
        file_entry = self._GetPasswordsFileEntry()

        test_data_stream_writer = data_stream_writer.DataStreamWriter()
        hash_value, file_object, file_data = (
            test_data_stream_writer.CalculateHashAndReadData(file_entry, "")
        )

        expected_hash = hashlib.sha256(self._FILE_DATA).hexdigest()
        self.assertEqual(hash_value, expected_hash)
        self.assertIsNotNone(file_object)
        self.assertEqual(file_data, self._FILE_DATA)

        test_data_stream_writer = _SmallBufferDataStreamWriter()
        hash_value, file_object, file_data = (
            test_data_stream_writer.CalculateHashAndReadData(file_entry, "")
        )

        self.assertEqual(hash_value, expected_hash)
        self.assertIsNotNone(file_object)
        self.assertIsNone(file_data)

    def testCalculateHashAndReadDataEmpty(self):
        """Tests the CalculateHashAndReadData function with an empty data stream."""
        file_entry = _FakeFileEntry(io.BytesIO(b""))

        test_data_stream_writer = data_stream_writer.DataStreamWriter()
        hash_value, _, file_data = test_data_stream_writer.CalculateHashAndReadData(
            file_entry, ""
        )

        self.assertEqual(hash_value, hashlib.sha256(b"").hexdigest())
        self.assertEqual(file_data, b"")

    def testCalculateHashAndReadDataMissing(self):
        """Tests the CalculateHashAndReadData function without a data stream."""
        file_entry = _FakeFileEntry(None)

        test_data_stream_writer = data_stream_writer.DataStreamWriter()
        with self.assertRaises(OSError):
            test_data_stream_writer.CalculateHashAndReadData(file_entry, "")

    def testWriteFileObject(self):
        """Tests the WriteFileObject function."""
        file_entry = self._GetPasswordsFileEntry()

        for test_data_stream_writer in (
            data_stream_writer.DataStreamWriter(),
            _SmallBufferDataStreamWriter(),
        ):
            _, file_object, file_data = (
                test_data_stream_writer.CalculateHashAndReadData(file_entry, "")
            )

            with test_lib.TempDirectory() as temp_directory:
                destination_path = os.path.join(temp_directory, "passwords.txt")
                test_data_stream_writer.WriteFileObject(
                    file_object, destination_path, data=file_data
                )

                with open(destination_path, "rb") as destination_file_object:
                    written_data = destination_file_object.read()

            self.assertEqual(written_data, self._FILE_DATA)

    def testWriteFileObjectEmpty(self):
        """Tests the WriteFileObject function with an empty data stream."""
        file_entry = _FakeFileEntry(io.BytesIO(b""))

        test_data_stream_writer = data_stream_writer.DataStreamWriter()
        _, file_object, file_data = test_data_stream_writer.CalculateHashAndReadData(
            file_entry, ""
        )

        with test_lib.TempDirectory() as temp_directory:
            destination_path = os.path.join(temp_directory, "empty")
            test_data_stream_writer.WriteFileObject(
                file_object, destination_path, data=file_data
            )

            self.assertTrue(os.path.isfile(destination_path))
            self.assertEqual(os.path.getsize(destination_path), 0)


if __name__ == "__main__":
    unittest.main()
