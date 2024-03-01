#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Console script to analyze sources."""

import argparse
import logging
import sys

from dfvfs.helpers import command_line as dfvfs_command_line
from dfvfs.lib import errors as dfvfs_errors

from dfimagetools import source_analyzer
from dfimagetools.helpers import backend


def Main():
  """Entry point of console script to analyze sources.

  Returns:
    int: exit code that is provided to sys.exit().
  """
  argument_parser = argparse.ArgumentParser(description=(
      'Analyzes volumes and file systems in a storage media image.'))

  argument_parser.add_argument(
      '--back_end', '--back-end', dest='back_end', action='store',
      metavar='NTFS', default=None, help='preferred dfVFS back-end.')

  argument_parser.add_argument(
      '--no-auto-recurse', '--no_auto_recurse', dest='no_auto_recurse',
      action='store_true', default=False, help=(
          'Indicate that the source scanner should not auto-recurse.'))

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

  backend.SetDFVFSBackEnd(options.back_end)

  logging.basicConfig(
      level=logging.INFO, format='[%(levelname)s] %(message)s')

  mediator = dfvfs_command_line.CLIVolumeScannerMediator()

  analyzer = source_analyzer.SourceAnalyzer(
      auto_recurse=not options.no_auto_recurse, mediator=mediator)

  try:
    scan_step = 0
    for scan_context in analyzer.Analyze(options.source):
      if options.no_auto_recurse:
        print(f'Scan step: {scan_step:d}')

      print(f'Source type\t\t: {scan_context.source_type:s}')
      print('')

      scan_node = scan_context.GetRootScanNode()
      analyzer.WriteScanNode(scan_context, scan_node)
      print('')

      scan_step += 1

    print('Completed.')

  except (KeyboardInterrupt, dfvfs_errors.UserAbort):
    print('Aborted by user.')
    return 1

  return 0


if __name__ == '__main__':
  sys.exit(Main())
