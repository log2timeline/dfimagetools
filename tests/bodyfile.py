#!/usr/bin/env python3
"""Tests for the helper to generating bodyfile entries."""

import random
import unittest

from dfdatetime import definitions as dfdatetime_definitions
from dfdatetime import filetime as dfdatetime_filetime
from dfdatetime import posix_time as dfdatetime_posix_time

from dfvfs.lib import definitions as dfvfs_definitions
from dfvfs.resolver import resolver
from dfvfs.path import factory as path_spec_factory

from dfimagetools import bodyfile
from dfimagetools import file_entry_lister

from tests import test_lib


class BodyfileGeneratorTest(test_lib.BaseTestCase):
    """Tests for the bodyfile generator."""

    # pylint: disable=protected-access

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

    def _GetExpectedTimestamp(self, test_bodyfile_generator, date_time):
        """Retrieves the expected bodyfile timestamp representation.

        Args:
          test_bodyfile_generator (BodyfileGenerator): bodyfile generator.
          date_time (dfdatetime.DateTimeValues): date time value.

        Returns:
          str: bodyfile timestamp representation of the date time value.
        """
        if not date_time or date_time.timestamp == 0:
            return ""

        posix_timestamp, fraction_of_second = (
            date_time.CopyToPosixTimestampWithFractionOfSecond()
        )
        format_string = test_bodyfile_generator._TIMESTAMP_FORMAT_STRINGS.get(
            date_time.precision, "{0:d}"
        )
        return format_string.format(posix_timestamp, fraction_of_second)

    def testGetTimestamp(self):
        """Tests the _GetTimestamp function."""
        test_bodyfile_generator = bodyfile.BodyfileGenerator()

        test_random = random.Random(0)

        filetime_posix_epoch = 116444736000000000
        uint64_max = (1 << 64) - 1

        filetime_timestamps = [
            1,
            filetime_posix_epoch - 1,
            filetime_posix_epoch,
            filetime_posix_epoch + 1,
            uint64_max,
        ]
        filetime_timestamps.extend(
            test_random.randint(0, uint64_max) for _ in range(250)
        )

        posix_time_timestamps = [-(1 << 63), -1, 1, (1 << 63) - 1, uint64_max]
        posix_time_timestamps.extend(
            test_random.randint(-(1 << 63), uint64_max) for _ in range(250)
        )

        test_values = [
            (dfdatetime_filetime.Filetime, filetime_timestamps),
            (dfdatetime_posix_time.PosixTime, posix_time_timestamps),
            (dfdatetime_posix_time.PosixTimeInMicroseconds, posix_time_timestamps),
            (dfdatetime_posix_time.PosixTimeInNanoseconds, posix_time_timestamps),
        ]
        for date_time_class, timestamps in test_values:
            for timestamp in timestamps:
                for time_zone_offset in (None, 0, 60, -60):
                    date_time = date_time_class(
                        time_zone_offset=time_zone_offset, timestamp=timestamp
                    )
                    expected_timestamp = self._GetExpectedTimestamp(
                        test_bodyfile_generator, date_time
                    )

                    date_time = date_time_class(
                        time_zone_offset=time_zone_offset, timestamp=timestamp
                    )
                    bodyfile_timestamp = test_bodyfile_generator._GetTimestamp(
                        date_time
                    )
                    self.assertEqual(bodyfile_timestamp, expected_timestamp)

        date_time = dfdatetime_filetime.Filetime(timestamp=filetime_posix_epoch)
        bodyfile_timestamp = test_bodyfile_generator._GetTimestamp(date_time)
        self.assertEqual(bodyfile_timestamp, "0.0000000")

        date_time = dfdatetime_posix_time.PosixTimeInMicroseconds(
            timestamp=1337961653000001
        )
        bodyfile_timestamp = test_bodyfile_generator._GetTimestamp(date_time)
        self.assertEqual(bodyfile_timestamp, "1337961653.000001")

        date_time = dfdatetime_posix_time.PosixTime(
            time_zone_offset=60, timestamp=1337961653
        )
        bodyfile_timestamp = test_bodyfile_generator._GetTimestamp(date_time)
        self.assertEqual(bodyfile_timestamp, "1337958053")

        date_time = dfdatetime_posix_time.PosixTimeInMicroseconds(
            precision=dfdatetime_definitions.PRECISION_1_MILLISECOND,
            timestamp=1337961653123456,
        )
        bodyfile_timestamp = test_bodyfile_generator._GetTimestamp(date_time)
        self.assertEqual(bodyfile_timestamp, "1337961653.123")

        bodyfile_timestamp = test_bodyfile_generator._GetTimestamp(None)
        self.assertEqual(bodyfile_timestamp, "")

        date_time = dfdatetime_posix_time.PosixTime(timestamp=0)
        bodyfile_timestamp = test_bodyfile_generator._GetTimestamp(date_time)
        self.assertEqual(bodyfile_timestamp, "")

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
