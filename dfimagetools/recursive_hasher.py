#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Helper to recursively calculate a message digest hash of data streams."""

import hashlib
import logging

from dfimagetools import definitions


class RecursiveHasher(object):
  """Recursively calculates message digest hashes of data streams."""

  # Class constant that defines the default read buffer size.
  _READ_BUFFER_SIZE = 16 * 1024 * 1024

  # List of tuple that contain:
  #    tuple: full path represented as a tuple of path segments
  #    str: data stream name
  _PATHS_TO_IGNORE = frozenset([
      (('$BadClus', ), '$Bad')])

  def _CalculateHashDataStream(self, file_entry, data_stream_name):
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

    hash_context = hashlib.sha256()

    try:
      file_object = file_entry.GetFileObject(data_stream_name=data_stream_name)
    except IOError as exception:
      path_specification_string = file_entry.path_spec.comparable.translate(
          definitions.NON_PRINTABLE_CHARACTER_TRANSLATION_TABLE)
      logging.warning((
          'Unable to open path specification:\n{0:s}'
          'with error: {1!s}').format(path_specification_string, exception))
      return None

    if not file_object:
      return None

    try:
      data = file_object.read(self._READ_BUFFER_SIZE)
      while data:
        hash_context.update(data)
        data = file_object.read(self._READ_BUFFER_SIZE)
    except IOError as exception:
      path_specification_string = file_entry.path_spec.comparable.translate(
          definitions.NON_PRINTABLE_CHARACTER_TRANSLATION_TABLE)
      logging.warning((
          'Unable to read from path specification:\n{0:s}'
          'with error: {1!s}').format(path_specification_string, exception))
      return None

    return hash_context.hexdigest()

  def _GetDisplayPath(self, path_segments, data_stream_name):
    """Retrieves a path to display.

    Args:
      path_segments (list[str]): path segments of the full path of the file
          entry.
      data_stream_name (str): name of the data stream.

    Returns:
      str: path to display.
    """
    display_path = ''

    path_segments = [
        segment.translate(definitions.NON_PRINTABLE_CHARACTER_TRANSLATION_TABLE)
        for segment in path_segments]
    display_path = ''.join([display_path, '/'.join(path_segments)])

    if data_stream_name:
      data_stream_name = data_stream_name.translate(
          definitions.NON_PRINTABLE_CHARACTER_TRANSLATION_TABLE)
      display_path = ':'.join([display_path, data_stream_name])

    return display_path or '/'

  def CalculateHashesFileEntry(self, file_entry, path_segments):
    """Recursive calculates hashes starting with the file entry.

    Args:
      file_entry (dfvfs.FileEntry): file entry.
      path_segments (str): path segments of the full path of file entry.

    Yields:
      tuple[str, str]: display path and hash value.
    """
    lookup_path = tuple(path_segments[1:])

    for data_stream in file_entry.data_streams:
      hash_value = None
      if (lookup_path, data_stream.name) not in self._PATHS_TO_IGNORE:
        hash_value = self._CalculateHashDataStream(file_entry, data_stream.name)

      display_path = self._GetDisplayPath(path_segments, data_stream.name)
      yield display_path, hash_value
