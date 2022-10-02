#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Script to map extents."""

import argparse
import logging
import sys

from dfvfs.lib import definitions as dfvfs_definitions
from dfvfs.helpers import command_line
from dfvfs.helpers import volume_scanner
from dfvfs.lib import errors

from dfimagetools import file_entry_lister
from dfimagetools import helpers


def Main():
  """The main program function.

  Returns:
    bool: True if successful or False if not.
  """
  argument_parser = argparse.ArgumentParser(description=(
      'Maps extents in a storage media image.'))

  argument_parser.add_argument(
      '--back_end', '--back-end', dest='back_end', action='store',
      metavar='NTFS', default=None, help='preferred dfVFS back-end.')

  argument_parser.add_argument(
      '--partitions', '--partition', dest='partitions', action='store',
      type=str, default=None, help=(
          'Define partitions to be processed. A range of partitions can be '
          'defined as: "3..5". Multiple partitions can be defined as: "1,3,5" '
          '(a list of comma separated values). Ranges and lists can also be '
          'combined as: "1,3..5". The first partition is 1. All partitions '
          'can be specified with: "all".'))

  argument_parser.add_argument(
      '--snapshots', '--snapshot', dest='snapshots', action='store', type=str,
      default=None, help=(
          'Define snapshots to be processed. A range of snapshots can be '
          'defined as: "3..5". Multiple snapshots can be defined as: "1,3,5" '
          '(a list of comma separated values). Ranges and lists can also be '
          'combined as: "1,3..5". The first snapshot is 1. All snapshots can '
          'be specified with: "all".'))

  argument_parser.add_argument(
      '--volumes', '--volume', dest='volumes', action='store', type=str,
      default=None, help=(
          'Define volumes to be processed. A range of volumes can be defined '
          'as: "3..5". Multiple volumes can be defined as: "1,3,5" (a list '
          'of comma separated values). Ranges and lists can also be combined '
          'as: "1,3..5". The first volume is 1. All volumes can be specified '
          'with: "all".'))

  argument_parser.add_argument(
      'source', nargs='?', action='store', metavar='image.raw',
      default=None, help='path of the directory or storage media image.')

  options = argument_parser.parse_args()

  if not options.source:
    print('Source value is missing.')
    print('')
    argument_parser.print_help()
    print('')
    return False

  # TODO: add support to write extent map entry to a SQLite database

  helpers.SetDFVFSBackEnd(options.back_end)

  logging.basicConfig(
      level=logging.INFO, format='[%(levelname)s] %(message)s')

  mediator = command_line.CLIVolumeScannerMediator()

  volume_scanner_options = volume_scanner.VolumeScannerOptions()
  volume_scanner_options.partitions = mediator.ParseVolumeIdentifiersString(
      options.partitions)

  if options.snapshots == 'none':
    volume_scanner_options.snapshots = ['none']
  else:
    volume_scanner_options.snapshots = mediator.ParseVolumeIdentifiersString(
        options.snapshots)

  volume_scanner_options.volumes = mediator.ParseVolumeIdentifiersString(
      options.volumes)

  entry_lister = file_entry_lister.FileEntryLister(mediator=mediator)
  return_value = True

  try:
    base_path_specs = entry_lister.GetBasePathSpecs(
        options.source, options=volume_scanner_options)
    if not base_path_specs:
      print('No supported file system found in source.')
      print('')
      return False

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

  except errors.ScannerError as exception:
    return_value = False

    print(f'[ERROR] {exception!s}', file=sys.stderr)

  except KeyboardInterrupt:
    return_value = False

    print('Aborted by user.', file=sys.stderr)

  return return_value


if __name__ == '__main__':
  if not Main():
    sys.exit(1)
  else:
    sys.exit(0)
