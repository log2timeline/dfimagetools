#!/usr/bin/env python3
"""Helper to recursively calculate a message digest hash of data streams."""

import hashlib
import logging

from dfvfs.lib import errors as dfvfs_errors
from dfvfs.vfs import ntfs_attribute

from dfimagetools import definitions


class RecursiveHasher:
    """Recursively calculates message digest hashes of data streams."""

    _ESCAPE_CHARACTERS = {"/": "\\/", ":": "\\:", "\\": "\\\\"}

    _ESCAPE_CHARACTERS.update(definitions.NON_PRINTABLE_CHARACTERS)

    # The default read buffer size.
    _READ_BUFFER_SIZE = 16 * 1024 * 1024

    # List of tuple that contain:
    #    tuple: full path represented as a tuple of path segments
    #    str: data stream name
    _PATHS_TO_IGNORE = frozenset([(("$BadClus",), "$Bad")])

    def __init__(self, include_extended_attributes=False, stop_on_error=False):
        """Initializes a recursive hasher.

        Args:
          include_extended_attributes (Optional[bool]): True if extended attributes
              should be included.
          stop_on_error (Optional[bool]): True to stop on error.
        """
        super().__init__()
        self._escape_characters = str.maketrans(self._ESCAPE_CHARACTERS)
        self._include_extended_attributes = include_extended_attributes
        self._stop_on_error = stop_on_error

    def _CalculateHashDataStream(self, path_spec, file_object, data_stream_name):
        """Calculates a message digest hash of the data of the file entry.

        Args:
          path_spec (dfvfs.PathSpec): path specification.
          file_object (dfvfs.FileIO): file-like object.
          data_stream_name (str): name of the data stream.

        Returns:
          str: digest hash or None.
        """
        hash_context = hashlib.sha256()

        try:
            data = file_object.read(self._READ_BUFFER_SIZE)
            while data:
                hash_context.update(data)
                data = file_object.read(self._READ_BUFFER_SIZE)
        except OSError as exception:
            path_specification_string = path_spec.comparable.translate(
                self._escape_characters
            )
            if data_stream_name:
                error_message = (
                    f"Unable to read data stream: {data_stream_name:s} from path "
                    f"specification:\n{path_specification_string:s} with error: "
                    f"{exception!s}"
                )
            else:
                error_message = (
                    f"Unable to read default data stream from path specification:\n"
                    f"{path_specification_string:s} with error: {exception!s}"
                )

            if self._stop_on_error:
                raise RuntimeError(error_message)

            logging.warning(error_message)
            return "N/A (error)"

        return hash_context.hexdigest()

    def _CalculateHashFileEntry(self, file_entry, data_stream_name):
        """Calculates a message digest hash of the data of the file entry.

        Args:
          file_entry (dfvfs.FileEntry): file entry.
          data_stream_name (str): name of the data stream.

        Returns:
          str: digest hash or None.
        """
        if file_entry.IsDevice() or file_entry.IsPipe() or file_entry.IsSocket():
            # Ignore devices, FIFOs/pipes and sockets.
            return None

        try:
            file_object = file_entry.GetFileObject(data_stream_name=data_stream_name)
        except OSError as exception:
            path_specification_string = file_entry.path_spec.comparable.translate(
                self._escape_characters
            )
            error_message = (
                f"Unable to open path specification:\n{path_specification_string:s}"
                f"with error: {exception!s}"
            )
            if self._stop_on_error:
                raise RuntimeError(error_message)

            logging.warning(error_message)
            return "N/A (error)"

        if not file_object:
            return None

        return self._CalculateHashDataStream(
            file_entry.path_spec, file_object, data_stream_name
        )

    def _GetDisplayPath(self, path_segments, data_stream_name):
        """Retrieves a path to display.

        Args:
          path_segments (list[str]): path segments of the full path of the file
              entry.
          data_stream_name (str): name of the data stream.

        Returns:
          str: path to display.
        """
        display_path = ""

        path_segments = [
            segment.translate(self._escape_characters) for segment in path_segments
        ]
        display_path = "".join([display_path, "/".join(path_segments)])

        if data_stream_name:
            data_stream_name = data_stream_name.translate(self._escape_characters)
            display_path = ":".join([display_path, data_stream_name])

        return display_path or "/"

    def CalculateHashesFileEntry(self, file_entry, path_segments):
        """Recursive calculates hashes starting with the file entry.

        Args:
          file_entry (dfvfs.FileEntry): file entry.
          path_segments (str): path segments of the full path of file entry.

        Yields:
          tuple[str, str]: display path and hash value.
        """
        file_system = file_entry.GetFileSystem()
        location = getattr(file_entry.path_spec, "location", None)
        if location:
            lookup_path = tuple(file_system.SplitPath(location))
        else:
            lookup_path = tuple(path_segments[1:])

        data_stream_name = None

        try:
            for data_stream in file_entry.data_streams:
                data_stream_name = data_stream.name
                if (lookup_path, data_stream_name) in self._PATHS_TO_IGNORE:
                    hash_value = "N/A (skipped)"
                else:
                    hash_value = self._CalculateHashFileEntry(
                        file_entry, data_stream_name
                    )

                if hash_value:
                    display_path = self._GetDisplayPath(path_segments, data_stream_name)
                    yield display_path, hash_value

        except (OSError, dfvfs_errors.BackEndError) as exception:
            path_specification_string = file_entry.path_spec.comparable.translate(
                definitions.NON_PRINTABLE_CHARACTER_TRANSLATION_TABLE
            )
            error_message = (
                f"Unable to traverse data streams of path specification:\n"
                f"{path_specification_string:s}\nwith error: {exception!s}"
            )
            if self._stop_on_error:
                raise RuntimeError(error_message)

            logging.warning(error_message)

            display_path = self._GetDisplayPath(path_segments, data_stream_name)
            yield display_path, "N/A (error)"

        if self._include_extended_attributes:
            try:
                for attribute in file_entry.attributes:
                    if isinstance(attribute, ntfs_attribute.NTFSAttribute):
                        continue

                    data_stream_name = getattr(attribute, "name", None)
                    hash_value = self._CalculateHashDataStream(
                        file_entry.path_spec, attribute, data_stream_name
                    )
                    display_path = self._GetDisplayPath(path_segments, data_stream_name)
                    yield display_path, hash_value

            except (OSError, dfvfs_errors.BackEndError) as exception:
                path_specification_string = file_entry.path_spec.comparable.translate(
                    definitions.NON_PRINTABLE_CHARACTER_TRANSLATION_TABLE
                )
                error_message = (
                    f"Unable to traverse extended attributes of path specification:\n"
                    f"{path_specification_string:s}\nwith error: {exception!s}"
                )
                if self._stop_on_error:
                    raise RuntimeError(error_message)

                logging.warning(error_message)

                display_path = self._GetDisplayPath(path_segments, data_stream_name)
                yield display_path, "N/A (error)"
