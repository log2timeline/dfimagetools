"""Helper for filtering based on file entry attributes."""

import abc
import collections

from dfdatetime import time_elements


class FileEntryFilter:
    """File entry filter interface."""

    # pylint: disable=redundant-returns-doc
    @abc.abstractmethod
    def Describe(self):
        """Retrieves a human readable description of the filter.

        Returns:
          list[str]: human readable description lines of the filter.
        """

    # pylint: disable=redundant-returns-doc
    @abc.abstractmethod
    def Matches(self, file_entry):
        """Compares the file entry against the filter.

        Args:
          file_entry (dfvfs.FileEntry): file entry to compare.

        Returns:
          bool: True if the file entry matches the filter, False if not or None
              if the filter does not apply.
        """


class DateTimeFileEntryFilter(FileEntryFilter):
    """Date and time-based file entry filter."""

    _DATE_TIME_RANGE_TUPLE = collections.namedtuple(
        "date_time_range_tuple", "time_value start_date_time end_date_time"
    )

    # Maps the time value of the date time range to a file entry attribute name.
    _TIME_VALUE_MAPPINGS = {
        "atime": "access_time",
        "bkup": "backup_time",
        "ctime": "change_time",
        "crtime": "creation_time",
        "dtime": "deletion_time",
        "mtime": "modification_time",
    }

    _SUPPORTED_TIME_VALUES = frozenset(_TIME_VALUE_MAPPINGS.keys())

    def __init__(self):
        """Initializes a date and time-based file entry filter."""
        super().__init__()
        self._date_time_ranges = []

    def AddDateTimeRange(
        self, time_value, start_time_string=None, end_time_string=None
    ):
        """Adds a date time filter range.

        The time strings are formatted as:
        YYYY-MM-DD hh:mm:ss.######[+-]##:##
        Where # are numeric digits ranging from 0 to 9 and the seconds
        fraction can be either 3 or 6 digits. The time of day, seconds fraction
        and timezone offset are optional. The default timezone is UTC.

        Args:
          time_value (str): time value, such as, atime, ctime, crtime, dtime,
              bkup and mtime.
          start_time_string (str): start date and time value string.
          end_time_string (str): end date and time value string.

        Raises:
          ValueError: if the filter is badly formed.
        """
        if not isinstance(time_value, str):
            raise ValueError("Filter type must be a string.")

        if not start_time_string and not end_time_string:
            raise ValueError(
                "Filter must have either a start or an end date time value."
            )

        time_value = time_value.lower()
        if time_value not in self._SUPPORTED_TIME_VALUES:
            raise ValueError(f"Unsupported time value: {time_value:s}.")

        start_date_time = None
        if start_time_string:
            start_date_time = time_elements.TimeElementsInMicroseconds()
            start_date_time.CopyFromDateTimeString(start_time_string)

        end_date_time = None
        if end_time_string:
            end_date_time = time_elements.TimeElementsInMicroseconds()
            end_date_time.CopyFromDateTimeString(end_time_string)

        # Make sure that the end timestamp occurs after the beginning.
        # If not then we need to reverse the time range.
        if (
            None not in (start_date_time, end_date_time)
            and start_date_time > end_date_time
        ):
            raise ValueError("Invalid date time value start must be earlier than end.")

        self._date_time_ranges.append(
            self._DATE_TIME_RANGE_TUPLE(time_value, start_date_time, end_date_time)
        )

    def Describe(self):
        """Retrieves a human readable description of the filter.

        Returns:
          list[str]: human readable description lines of the filter.
        """
        lines = []
        for date_time_range in self._date_time_ranges:
            if date_time_range.start_date_time is None:
                end_time_string = date_time_range.end_date_time.CopyToDateTimeString()
                lines.append(
                    f"\t{date_time_range.time_value:s} after {end_time_string:s}"
                )

            elif date_time_range.end_date_time is None:
                start_time_string = (
                    date_time_range.start_date_time.CopyToDateTimeString()
                )
                lines.append(
                    f"\t{date_time_range.time_value:s} before {start_time_string:s}"
                )

            else:
                start_time_string = (
                    date_time_range.start_date_time.CopyToDateTimeString()
                )
                end_time_string = date_time_range.end_date_time.CopyToDateTimeString()
                lines.append(
                    f"\t{date_time_range.time_value:s} between {start_time_string:s} "
                    f"and {end_time_string:s}"
                )

        return lines

    def Matches(self, file_entry):
        """Compares the file entry against the filter.

        Args:
          file_entry (dfvfs.FileEntry): file entry to compare.

        Returns:
          bool: True if the file entry matches the filter, False if not or
              None if the filter does not apply.
        """
        if not self._date_time_ranges:
            return None

        for date_time_range in self._date_time_ranges:
            time_attribute = self._TIME_VALUE_MAPPINGS.get(
                date_time_range.time_value, None
            )
            if not time_attribute:
                continue

            timestamp = getattr(file_entry, time_attribute, None)
            if timestamp is None:
                continue

            if (
                date_time_range.start_date_time is not None
                and timestamp < date_time_range.start_date_time
            ):
                return False

            if (
                date_time_range.end_date_time is not None
                and timestamp > date_time_range.end_date_time
            ):
                return False

        return True


class ExtensionsFileEntryFilter(FileEntryFilter):
    """Extensions-based file entry filter."""

    def __init__(self, extensions):
        """Initializes an extensions-based file entry filter.

        An extension is defined as "pdf" as in "document.pdf".

        Args:
          extensions (list[str]): a list of extension strings.
        """
        super().__init__()
        self._extensions = extensions

    def Describe(self):
        """Retrieves a human readable description of the filter.

        Returns:
          list[str]: human readable description lines of the filter.
        """
        if not self._extensions:
            return []

        extensions = ", ".join(self._extensions)
        return [f"\textensions: {extensions:s}"]

    def Matches(self, file_entry):
        """Compares the file entry against the filter.

        Args:
          file_entry (dfvfs.FileEntry): file entry to compare.

        Returns:
          bool: True if the file entry matches the filter, False if not or
              None if the filter does not apply.
        """
        location = getattr(file_entry.path_spec, "location", None)
        if not location:
            return None

        if "." not in location:
            return False

        _, _, extension = location.rpartition(".")
        return extension.lower() in self._extensions


class NamesFileEntryFilter(FileEntryFilter):
    """Names-based file entry filter."""

    def __init__(self, names):
        """Initializes a names-based file entry filter.

        Args:
          names (list[str]): names.
        """
        super().__init__()
        self._names = names

    def Describe(self):
        """Retrieves a human readable description of the filter.

        Returns:
          list[str]: human readable description lines of the filter.
        """
        if not self._names:
            return []

        names = ", ".join(self._names)
        return [f"\tnames: {names:s}"]

    def Matches(self, file_entry):
        """Compares the file entry against the filter.

        Args:
          file_entry (dfvfs.FileEntry): file entry to compare.

        Returns:
          bool: True if the file entry matches the filter.
        """
        if not self._names or not file_entry.IsFile():
            return False

        return file_entry.name.lower() in self._names


class FileEntryFilterCollection:
    """Collection of file entry filters."""

    def __init__(self):
        """Initializes a collection of file entry filters."""
        super().__init__()
        self._filters = []

    def AddFilter(self, file_entry_filter):
        """Adds a file entry filter to the collection.

        Args:
          file_entry_filter (FileEntryFilter): file entry filter.
        """
        self._filters.append(file_entry_filter)

    def Describe(self):
        """Retrieves a human readable description of the collection.

        Returns:
          list[str]: human readable description lines of the collection.
        """
        lines = []
        for file_entry_filter in self._filters:
            lines.extend(file_entry_filter.Describe())

        return lines

    def HasFilters(self):
        """Determines if filters are defined.

        Returns:
          bool: True if filters are defined.
        """
        return bool(self._filters)

    def Matches(self, file_entry):
        """Compares the file entry against the filter collection.

        Args:
          file_entry (dfvfs.FileEntry): file entry to compare.

        Returns:
          bool: True if the file entry matches one of the filters. If no filters
              are provided or applicable the result will be True.
        """
        if not self._filters:
            return True

        results = []
        for file_entry_filter in self._filters:
            result = file_entry_filter.Matches(file_entry)
            results.append(result)

        return True in results or False not in results
