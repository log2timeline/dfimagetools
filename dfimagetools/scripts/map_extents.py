#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Console script to map extents."""

import argparse
import logging
import sys

from dfvfs.lib import definitions as dfvfs_definitions
from dfvfs.lib import errors as dfvfs_errors

from dfimagetools import file_entry_lister
from dfimagetools.helpers import command_line


def Main():
  """Entry point of console script to map extents.

  Returns:
    int: exit code that is provided to sys.exit().
  """
  argument_parser = argparse.ArgumentParser(description=(
      'Maps extents in a storage media image.'))

  command_line.AddStorageMediaImageCLIArguments(argument_parser)

  argument_parser.add_argument(
      'source', nargs='?', action='store', metavar='image.raw',
      default=None, help='path of the directory or storage media image.')

  options = argument_parser.parse_args()

  if not options.source:
    print('Source value is missing.')
    print('')
    argument_parser.print_help()
    print('')
    return 1

  # TODO: add support to write extent map entry to a SQLite database

  logging.basicConfig(
      level=logging.INFO, format='[%(levelname)s] %(message)s')

  mediator, volume_scanner_options = (
      command_line.ParseStorageMediaImageCLIArguments(options))

  entry_lister = file_entry_lister.FileEntryLister(mediator=mediator)

  try:
    base_path_specs = entry_lister.GetBasePathSpecs(
        options.source, options=volume_scanner_options)
    if not base_path_specs:
      print('No supported file system found in source.')
      print('')
      return 1

    # TODO: error if not a storage media image or device

    print('Start offset\tEnd offset\tExtent type\tPath hint')

    for file_entry, path_segments in entry_lister.ListFileEntries(
        base_path_specs):

      path = '/'.join(path_segments) or '/'

      for data_stream in file_entry.data_streams:
        # Ignore the WofCompressedData data stream since the NTFS back-end
        # has built-in support for Windows Overlay Filter (WOF) compression.
        if (data_stream.name == 'WofCompressedData' and
            file_entry.type_indicator == dfvfs_definitions.TYPE_INDICATOR_NTFS):
          continue

        if data_stream.name:
          extent_type = 'DATA_STREAM'
          data_stream_path = ':'.join([path, data_stream.name])
        else:
          extent_type = 'FILE_CONTENT'
          data_stream_path = path

        for extent in data_stream.GetExtents():
          if extent.extent_type != dfvfs_definitions.EXTENT_TYPE_SPARSE:
            extent_end_offset = extent.offset + extent.size
            print(f'0x{extent.offset:08x}\t0x{extent_end_offset:08x}\t'
                  f'{extent_type:s}\t{data_stream_path:s}')

  except dfvfs_errors.ScannerError as exception:
    print(f'[ERROR] {exception!s}', file=sys.stderr)
    return 1

  except (KeyboardInterrupt, dfvfs_errors.UserAbort):
    print('Aborted by user.', file=sys.stderr)
    return 1

  return 0


if __name__ == '__main__':
  sys.exit(Main())
