#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Console script to recursive hash data streams."""

import argparse
import logging
import sys

from dfvfs.lib import errors as dfvfs_errors

from dfimagetools import file_entry_lister
from dfimagetools import recursive_hasher
from dfimagetools.helpers import command_line


def Main():
  """Entry point for console script to recursive hash data streams.

  Returns:
    int: exit code that is provided to sys.exit().
  """
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
    return 1

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
      return 1

    hasher = recursive_hasher.RecursiveHasher()
    for base_path_spec in base_path_specs:
      file_entries_generator = entry_lister.ListFileEntries([base_path_spec])

      for file_entry, path_segments in file_entries_generator:
        for display_path, hash_value in hasher.CalculateHashesFileEntry(
            file_entry, path_segments):
          print('{0:s}\t{1:s}'.format(hash_value or 'N/A', display_path))

  except dfvfs_errors.ScannerError as exception:
    print(f'[ERROR] {exception!s}', file=sys.stderr)
    print('')
    return 1

  except (KeyboardInterrupt, dfvfs_errors.UserAbort):
    print('Aborted by user.', file=sys.stderr)
    print('')
    return 1

  return 0


if __name__ == '__main__':
  sys.exit(Main())
