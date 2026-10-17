#!/usr/bin/env python3
"""Tests for the file entry filters."""

import unittest

from dfdatetime import time_elements

from dfimagetools import file_entry_filters

from tests import test_lib


class FakePathSpec:
    """Fake path specification."""

    def __init__(self, location):
        """Initializes a fake path specification.

        Args:
          location (str): location.
        """
        super().__init__()
        self.location = location


class FakeFileEntry:
    """Fake file entry."""

    def __init__(self, name="file.txt", location=None, is_file=True):
        """Initializes a fake file entry.

        Args:
          name (str): name of the file entry.
          location (str): location of the file entry within the file system.
          is_file (bool): True if the file entry is a file.
        """
        super().__init__()
        self._is_file = is_file
        self.access_time = None
        self.name = name
        self.path_spec = FakePathSpec(location)

    def IsFile(self):
        """Determines if the file entry is a file.

        Returns:
          bool: True if the file entry is a file.
        """
        return self._is_file


class DateTimeFileEntryFilterTest(test_lib.BaseTestCase):
    """Tests for the date time file entry filter."""

    def _SetAccessTime(self, file_entry, date_time_string):
        """Sets the access time of a fake file entry.

        Args:
          file_entry (FakeFileEntry): fake file entry.
          date_time_string (str): date and time value string.
        """
        access_time = time_elements.TimeElementsInMicroseconds()
        access_time.CopyFromDateTimeString(date_time_string)
        file_entry.access_time = access_time

    def testAddDateTimeRange(self):
        """Tests the AddDateTimeRange function."""
        test_filter = file_entry_filters.DateTimeFileEntryFilter()
        test_filter.AddDateTimeRange("atime", start_time_string="2023-01-01 00:00:00")

        test_filter.AddDateTimeRange(
            "mtime",
            start_time_string="2023-01-01 00:00:00",
            end_time_string="2023-02-01 00:00:00",
        )

        self.assertEqual(len(test_filter.Describe()), 2)

    def testAddDateTimeRangeInvalidTimeValue(self):
        """Tests the AddDateTimeRange function with an invalid time value."""
        test_filter = file_entry_filters.DateTimeFileEntryFilter()

        with self.assertRaises(ValueError):
            test_filter.AddDateTimeRange(
                "mtimee", start_time_string="2023-01-01 00:00:00"
            )

    def testAddDateTimeRangeNoTimestamp(self):
        """Tests the AddDateTimeRange function without start and end timestamp."""
        test_filter = file_entry_filters.DateTimeFileEntryFilter()

        with self.assertRaises(ValueError):
            test_filter.AddDateTimeRange("atime")

    def testAddDateTimeRangeEndBeforeStart(self):
        """Tests the AddDateTimeRange function with an end before the start."""
        test_filter = file_entry_filters.DateTimeFileEntryFilter()

        with self.assertRaises(ValueError):
            test_filter.AddDateTimeRange(
                "atime",
                start_time_string="2023-02-01 00:00:00",
                end_time_string="2023-01-01 00:00:00",
            )

    def testMatchesWithinRange(self):
        """Tests the Matches function with an access time within the range."""
        test_filter = file_entry_filters.DateTimeFileEntryFilter()
        test_filter.AddDateTimeRange(
            "atime",
            start_time_string="2023-01-01 00:00:00",
            end_time_string="2023-02-01 00:00:00",
        )

        test_file_entry = FakeFileEntry()
        self._SetAccessTime(test_file_entry, "2023-01-15 10:30:00")

        self.assertTrue(test_filter.Matches(test_file_entry))

    def testMatchesOutsideRange(self):
        """Tests the Matches function with an access time outside the range."""
        test_filter = file_entry_filters.DateTimeFileEntryFilter()
        test_filter.AddDateTimeRange(
            "atime",
            start_time_string="2023-01-01 00:00:00",
            end_time_string="2023-02-01 00:00:00",
        )

        test_file_entry = FakeFileEntry()
        self._SetAccessTime(test_file_entry, "2023-03-01 00:00:00")

        self.assertFalse(test_filter.Matches(test_file_entry))

    def testMatchesNoTimestamp(self):
        """Tests the Matches function if the file entry has no timestamp."""
        test_filter = file_entry_filters.DateTimeFileEntryFilter()
        test_filter.AddDateTimeRange(
            "atime",
            start_time_string="2023-01-01 00:00:00",
            end_time_string="2023-02-01 00:00:00",
        )

        # A file entry without a timestamp for the time value is not matched
        # against the range.
        test_file_entry = FakeFileEntry()
        self.assertTrue(test_filter.Matches(test_file_entry))

    def testMatchesNoDateTimes(self):
        """Tests the Matches function without date times."""
        test_filter = file_entry_filters.DateTimeFileEntryFilter()

        test_file_entry = FakeFileEntry()
        self.assertIsNone(test_filter.Matches(test_file_entry))


class ExtensionsFileEntryFilterTest(test_lib.BaseTestCase):
    """Tests for the extensions file entry filter."""

    def testMatches(self):
        """Tests the Matches function."""
        test_filter = file_entry_filters.ExtensionsFileEntryFilter(["evtx", "json"])

        test_file_entry = FakeFileEntry(
            name="application.evtx", location="/dir/application.evtx"
        )
        self.assertTrue(test_filter.Matches(test_file_entry))

        test_file_entry = FakeFileEntry(
            name="application.JSON", location="/dir/application.JSON"
        )
        self.assertTrue(test_filter.Matches(test_file_entry))

        test_file_entry = FakeFileEntry(
            name="application.txt", location="/dir/application.txt"
        )
        self.assertFalse(test_filter.Matches(test_file_entry))

        # A file entry without an extension is not matched.
        test_file_entry = FakeFileEntry(name="document", location="/dir/document")
        self.assertFalse(test_filter.Matches(test_file_entry))

    def testMatchesNoLocation(self):
        """Tests the Matches function with a file entry without a location."""
        test_filter = file_entry_filters.ExtensionsFileEntryFilter(["evtx"])

        test_file_entry = FakeFileEntry()
        self.assertIsNone(test_filter.Matches(test_file_entry))


class NamesFileEntryFilterTest(test_lib.BaseTestCase):
    """Tests for the names file entry filter."""

    def testMatches(self):
        """Tests the Matches function."""
        test_filter = file_entry_filters.NamesFileEntryFilter(
            ["ntuser.dat", "usrclass.dat"]
        )

        test_file_entry = FakeFileEntry(name="NTUSER.DAT")
        self.assertTrue(test_filter.Matches(test_file_entry))

        test_file_entry = FakeFileEntry(name="NTUSER.LOG2")
        self.assertFalse(test_filter.Matches(test_file_entry))

        # A directory entry is not matched by a names filter.
        test_file_entry = FakeFileEntry(name="NTUSER.DAT", is_file=False)
        self.assertFalse(test_filter.Matches(test_file_entry))


class FileEntryFilterCollectionTest(test_lib.BaseTestCase):
    """Tests for the file entry filter collection."""

    def testDescribe(self):
        """Tests the Describe function."""
        test_filter_collection = file_entry_filters.FileEntryFilterCollection()
        test_filter_collection.AddFilter(
            file_entry_filters.NamesFileEntryFilter(["ntuser.dat"])
        )
        test_filter_collection.AddFilter(
            file_entry_filters.ExtensionsFileEntryFilter(["evtx"])
        )

        self.assertEqual(
            test_filter_collection.Describe(),
            ["\tnames: ntuser.dat", "\textensions: evtx"],
        )

    def testHasFilters(self):
        """Tests the HasFilters function."""
        test_filter_collection = file_entry_filters.FileEntryFilterCollection()
        self.assertFalse(test_filter_collection.HasFilters())

        test_filter_collection.AddFilter(
            file_entry_filters.NamesFileEntryFilter(["ntuser.dat"])
        )
        self.assertTrue(test_filter_collection.HasFilters())

    def testMatches(self):
        """Tests the Matches function."""
        test_filter_collection = file_entry_filters.FileEntryFilterCollection()
        test_filter_collection.AddFilter(
            file_entry_filters.NamesFileEntryFilter(["ntuser.dat"])
        )
        test_filter_collection.AddFilter(
            file_entry_filters.ExtensionsFileEntryFilter(["evtx"])
        )

        # The file entry matches the names filter.
        test_file_entry = FakeFileEntry(name="NTUSER.DAT", location="/dir/NTUSER.DAT")
        self.assertTrue(test_filter_collection.Matches(test_file_entry))

        # The file entry matches the extensions filter.
        test_file_entry = FakeFileEntry(
            name="application.evtx", location="/dir/application.evtx"
        )
        self.assertTrue(test_filter_collection.Matches(test_file_entry))

        # The file entry does not match either of the filters.
        test_file_entry = FakeFileEntry(name="NOTUSER.DAT", location="/dir/NOTUSER.DAT")
        self.assertFalse(test_filter_collection.Matches(test_file_entry))

        # A directory entry does not match the names filter and has no
        # extension.
        test_file_entry = FakeFileEntry(
            name="logs", location="/dir/logs", is_file=False
        )
        self.assertFalse(test_filter_collection.Matches(test_file_entry))

    def testMatchesNoFilters(self):
        """Tests the Matches function without filters."""
        test_filter_collection = file_entry_filters.FileEntryFilterCollection()

        test_file_entry = FakeFileEntry(name="NTUSER.DAT")
        self.assertTrue(test_filter_collection.Matches(test_file_entry))


if __name__ == "__main__":
    unittest.main()
