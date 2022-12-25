#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Script to analyze volumes and file systems in a storage media image."""

import argparse
import logging
import sys

from dfvfs.helpers import command_line
from dfvfs.lib import definitions as dfvfs_definitions
from dfvfs.resolver import resolver

from dfimagetools import helpers
from dfimagetools import source_analyzer


def WriteScanNode(scan_context, scan_node, indentation=''):
  """Writes the source scanner node to stdout.

  Args:
    scan_context (dfvfs.SourceScannerContext): the source scanner context.
    scan_node (dfvfs.SourceScanNode): the scan node.
    indentation (Optional[str]): indentation.
  """
  if not scan_node:
    return

  values = []

  part_index = getattr(scan_node.path_spec, 'part_index', None)
  if part_index is not None:
    values.append(f'{part_index:d}')

  store_index = getattr(scan_node.path_spec, 'store_index', None)
  if store_index is not None:
    values.append(f'{store_index:d}')

  start_offset = getattr(scan_node.path_spec, 'start_offset', None)
  if start_offset is not None:
    values.append(f'start offset: {start_offset:d} (0x{start_offset:08x})')

  location = getattr(scan_node.path_spec, 'location', None)
  if location is not None:
    values.append(f'location: {location:s}')

  values = ', '.join(values)

  flags = []
  if scan_node in scan_context.locked_scan_nodes:
    flags.append(' [LOCKED]')

  type_indicator = scan_node.path_spec.type_indicator
  if type_indicator == dfvfs_definitions.TYPE_INDICATOR_TSK:
    file_system = resolver.Resolver.OpenFileSystem(scan_node.path_spec)
    if file_system.IsHFS():
      flags.append('[HFS/HFS+/HFSX]')
    elif file_system.IsNTFS():
      flags.append('[NTFS]')

  flags = ' '.join(flags)
  print(f'{indentation:s}{type_indicator:s}: {values:s}{flags:s}')

  indentation = f'  {indentation:s}'
  for sub_scan_node in scan_node.sub_nodes:
    WriteScanNode(scan_context, sub_scan_node, indentation=indentation)


def Main():
  """The main program function.

  Returns:
    bool: True if successful or False if not.
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
    return False

  helpers.SetDFVFSBackEnd(options.back_end)

  logging.basicConfig(
      level=logging.INFO, format='[%(levelname)s] %(message)s')

  mediator = command_line.CLIVolumeScannerMediator()

  analyzer = source_analyzer.SourceAnalyzer(
      auto_recurse=not options.no_auto_recurse, mediator=mediator)

  return_value = True

  try:
    scan_step = 0
    for scan_context in analyzer.Analyze(options.source):
      if options.no_auto_recurse:
        print(f'Scan step: {scan_step:d}')

      print(f'Source type\t\t: {scan_context.source_type:s}')
      print('')

      scan_node = scan_context.GetRootScanNode()
      WriteScanNode(scan_context, scan_node)
      print('')

      scan_step += 1

    print('Completed.')

  except KeyboardInterrupt:
    return_value = False

    print('Aborted by user.')

  return return_value


if __name__ == '__main__':
  if not Main():
    sys.exit(1)
  else:
    sys.exit(0)
