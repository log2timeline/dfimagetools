#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Script to recursively calculate a message digest hash of data streams."""

import argparse
import hashlib
import logging
import sys

from dfvfs.lib import errors as dfvfs_errors

from dfimagetools import definitions
from dfimagetools import file_entry_lister
from dfimagetools.helpers import command_line


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


if __name__ == '__main__':
  argument_parser = argparse.ArgumentParser(description=(
      'Calculates a message digest hash for every file in a directory or '
      'storage media image.'))

  # TODO: add output group
  argument_parser.add_argument(
      '--no_aliases', '--no-aliases', dest='use_aliases', action='store_false',
      default=True, help=(
          'Disable the use of partition and/or volume aliases such as '
          '/apfs{f449e580-e355-4e74-8880-05e46e4e3b1e} and use indices '
          'such as /apfs1 instead.'))

  # TODO: add source group
  command_line.AddStorageMediaImageCLIArguments(argument_parser)

  argument_parser.add_argument(
      'source', nargs='?', action='store', metavar='image.raw',
      default=None, help='path of the storage media image.')

  options = argument_parser.parse_args()

  if not options.source:
    print('Source value is missing.')
    print('')
    argument_parser.print_help()
    print('')
    sys.exit(1)

  logging.basicConfig(
      level=logging.INFO, format='[%(levelname)s] %(message)s')

  mediator, volume_scanner_options = (
      command_line.ParseStorageMediaImageCLIArguments(options))

  entry_lister = file_entry_lister.FileEntryLister(
      mediator=mediator, use_aliases=options.use_aliases)

  try:
    base_path_specs = entry_lister.GetBasePathSpecs(
        options.source, options=volume_scanner_options)
    if not base_path_specs:
      print('No supported file system found in source.')
      print('')
      sys.exit(1)

    hasher = RecursiveHasher()
    for base_path_spec in base_path_specs:
      file_entries_generator = entry_lister.ListFileEntries([base_path_spec])

      for file_entry, path_segments in file_entries_generator:
        for display_path, hash_value in hasher.CalculateHashesFileEntry(
            file_entry, path_segments):
          print('{0:s}\t{1:s}'.format(hash_value or 'N/A', display_path))

  except dfvfs_errors.ScannerError as exception:
    print(f'[ERROR] {exception!s}', file=sys.stderr)
    print('')
    sys.exit(1)

  except KeyboardInterrupt:
    print('Aborted by user.', file=sys.stderr)
    print('')
    sys.exit(1)

  sys.exit(0)
