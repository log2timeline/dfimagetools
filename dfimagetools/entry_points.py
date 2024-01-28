#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Entry points of console scripts."""

import argparse
import logging
import os
import sys

from artifacts import reader as artifacts_reader
from artifacts import registry as artifacts_registry

from dfvfs.helpers import command_line as dfvfs_command_line
from dfvfs.lib import definitions as dfvfs_definitions
from dfvfs.lib import errors as dfvfs_errors

from dfimagetools import artifact_filters
from dfimagetools import bodyfile
from dfimagetools import data_stream_writer
from dfimagetools import file_entry_lister
from dfimagetools import recursive_hasher
from dfimagetools import source_analyzer
from dfimagetools import windows_registry
from dfimagetools.helpers import backend
from dfimagetools.helpers import command_line


def ExtractDataStreams():
  """Console script to extract data streams.

  Returns:
    int: exit code that is provided to sys.exit().
  """
  argument_parser = argparse.ArgumentParser(description=(
      'Extracts data streams from a storage media image.'))

  # TODO: add filter group
  argument_parser.add_argument(
      '--artifact_definitions', '--artifact-definitions',
      dest='artifact_definitions', type=str, metavar='PATH', action='store',
      help=('Path to a directory or file containing the artifact definition '
            '.yaml files.'))

  argument_parser.add_argument(
      '--artifact_filters', '--artifact-filters', dest='artifact_filters',
      type=str, default=None, metavar='NAMES', action='store', help=(
          'Comma separated list of names of artifact definitions to extract.'))

  argument_parser.add_argument(
      '--custom_artifact_definitions', '--custom-artifact-definitions',
      dest='custom_artifact_definitions', type=str, metavar='PATH',
      action='store', help=(
          'Path to a directory or file containing custom artifact definition '
          '.yaml files. '))

  # TODO: add output group
  argument_parser.add_argument(
      '-t', '--target', dest='target', action='store', metavar='PATH',
      default=None, help=(
          'target (or destination) path of a directory where the extracted '
          'data streams should be stored.'))

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

  if options.artifact_filters:
    if (not options.artifact_definitions and
        not options.custom_artifact_definitions):
      print('[ERROR] artifact filters were specified but no paths to '
            'artifact definitions were provided.')
      print('')
      return 1

  # TODO: improve this, for now this script needs at least 1 filter.
  if not options.artifact_filters:
    print('[ERROR] no artifact filters were specified.')
    print('')
    return 1

  target_path = options.target
  if not target_path:
    source_name = os.path.basename(options.source)
    target_path = os.path.join(os.getcwd(), f'{source_name:s}.extracted')

  if not os.path.exists(target_path):
    os.makedirs(target_path)

  elif not os.path.isdir(target_path):
    print('[ERROR] target path is not a directory.')
    print('')
    return 1

  logging.basicConfig(
      level=logging.INFO, format='[%(levelname)s] %(message)s')

  mediator, volume_scanner_options = (
      command_line.ParseStorageMediaImageCLIArguments(options))

  if options.artifact_filters:
    registry = artifacts_registry.ArtifactDefinitionsRegistry()
    reader = artifacts_reader.YamlArtifactsReader()

    if options.artifact_definitions:
      if os.path.isdir(options.artifact_definitions):
        registry.ReadFromDirectory(reader, options.artifact_definitions)
      elif os.path.isfile(options.artifact_definitions):
        registry.ReadFromFile(reader, options.artifact_definitions)

    if options.custom_artifact_definitions:
      if os.path.isdir(options.custom_artifact_definitions):
        registry.ReadFromDirectory(
            reader, options.custom_artifact_definitions)
      elif os.path.isfile(options.custom_artifact_definitions):
        registry.ReadFromFile(reader, options.custom_artifact_definitions)

  entry_lister = file_entry_lister.FileEntryLister(mediator=mediator)
  find_specs_generated = False

  try:
    base_path_specs = entry_lister.GetBasePathSpecs(
        options.source, options=volume_scanner_options)
    if not base_path_specs:
      print('No supported file system found in source.')
      print('')
      return 1

    for base_path_spec in base_path_specs:
      if not options.artifact_filters:
        find_specs = []
      else:
        windows_directory = entry_lister.GetWindowsDirectory(base_path_spec)
        if not windows_directory:
          environment_variables = []
        else:
          winregistry_collector = windows_registry.WindowsRegistryCollector(
              base_path_spec, windows_directory)

          environment_variables = (
              winregistry_collector.CollectSystemEnvironmentVariables())

        filter_generator = artifact_filters.ArtifactDefinitionFiltersGenerator(
            registry, environment_variables, [])

        names = options.artifact_filters.split(',')
        find_specs = list(filter_generator.GetFindSpecs(names))
        if not find_specs:
          continue

        find_specs_generated = True

      file_entries_generator = entry_lister.ListFileEntriesWithFindSpecs(
          [base_path_spec], find_specs)

      stream_writer = data_stream_writer.DataStreamWriter()
      for file_entry, path_segments in file_entries_generator:
        for data_stream in file_entry.data_streams:
          display_path = stream_writer.GetDisplayPath(
              path_segments, data_stream.name)
          destination_path = stream_writer.GetSanitizedPath(
              path_segments, data_stream.name, target_path)
          logging.info(f'Extracting: {display_path:s} to: {destination_path:s}')

          destination_directory = os.path.dirname(destination_path)
          os.makedirs(destination_directory, exist_ok=True)

          stream_writer.WriteDataStream(
              file_entry, data_stream.name, destination_path)

  except dfvfs_errors.ScannerError as exception:
    print(f'[ERROR] {exception!s}', file=sys.stderr)
    print('')
    return 1

  except KeyboardInterrupt:
    print('Aborted by user.', file=sys.stderr)
    print('')
    return 1

  if options.artifact_filters and not find_specs_generated:
    print('[ERROR] an artifact filter was specified but no corresponding '
          'file system find specifications were generated.')
    print('')
    return 1

  return 0


def ListFileEntries():
  """Console script to list file entries.

  Returns:
    int: exit code that is provided to sys.exit().
  """
  argument_parser = argparse.ArgumentParser(description=(
      'Lists metadata of file entries in a storage media image.'))

  # TODO: add filter group
  argument_parser.add_argument(
      '--artifact_definitions', '--artifact-definitions',
      dest='artifact_definitions', type=str, metavar='PATH', action='store',
      help=('Path to a directory or file containing the artifact definition '
            '.yaml files.'))

  argument_parser.add_argument(
      '--artifact_filters', '--artifact-filters', dest='artifact_filters',
      type=str, default=None, metavar='NAMES', action='store', help=(
          'Comma separated list of names of artifact definitions to extract.'))

  argument_parser.add_argument(
      '--custom_artifact_definitions', '--custom-artifact-definitions',
      dest='custom_artifact_definitions', type=str, metavar='PATH',
      action='store', help=(
          'Path to a directory or file containing custom artifact definition '
          '.yaml files. '))

  # TODO: add output group
  argument_parser.add_argument(
      '--no_aliases', '--no-aliases', dest='use_aliases', action='store_false',
      default=True, help=(
          'Disable the use of partition and/or volume aliases such as '
          '/apfs{f449e580-e355-4e74-8880-05e46e4e3b1e} and use indices '
          'such as /apfs1 instead.'))

  argument_parser.add_argument(
      '--output_format', '--output-format', dest='output_format',
      action='store', metavar='FORMAT', default='bodyfile', help=(
          'output format, default is bodyfile.'))

  # TODO: add source group.
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

  if options.output_format != 'bodyfile':
    print(f'Unsupported output format: {options.output_format:s}.')
    print('')
    argument_parser.print_help()
    print('')
    return 1

  if options.artifact_filters:
    if (not options.artifact_definitions and
        not options.custom_artifact_definitions):
      print('[ERROR] artifact filters were specified but no paths to '
            'artifact definitions were provided.')
      print('')
      return 1

  logging.basicConfig(
      level=logging.INFO, format='[%(levelname)s] %(message)s')

  mediator, volume_scanner_options = (
      command_line.ParseStorageMediaImageCLIArguments(options))

  if options.artifact_filters:
    registry = artifacts_registry.ArtifactDefinitionsRegistry()
    reader = artifacts_reader.YamlArtifactsReader()

    if options.artifact_definitions:
      if os.path.isdir(options.artifact_definitions):
        registry.ReadFromDirectory(reader, options.artifact_definitions)
      elif os.path.isfile(options.artifact_definitions):
        registry.ReadFromFile(reader, options.artifact_definitions)

    if options.custom_artifact_definitions:
      if os.path.isdir(options.custom_artifact_definitions):
        registry.ReadFromDirectory(reader, options.custom_artifact_definitions)
      elif os.path.isfile(options.custom_artifact_definitions):
        registry.ReadFromFile(reader, options.custom_artifact_definitions)

  entry_lister = file_entry_lister.FileEntryLister(
      mediator=mediator, use_aliases=options.use_aliases)
  find_specs_generated = False

  try:
    base_path_specs = entry_lister.GetBasePathSpecs(
        options.source, options=volume_scanner_options)
    if not base_path_specs:
      print('No supported file system found in source.')
      print('')
      return 1

    bodyfile_header_printed = False

    for base_path_spec in base_path_specs:
      if not options.artifact_filters:
        find_specs = []
      else:
        windows_directory = entry_lister.GetWindowsDirectory(base_path_spec)
        if not windows_directory:
          environment_variables = []
        else:
          winregistry_collector = windows_registry.WindowsRegistryCollector(
              base_path_spec, windows_directory)

          environment_variables = (
              winregistry_collector.CollectSystemEnvironmentVariables())

        filter_generator = artifact_filters.ArtifactDefinitionFiltersGenerator(
            registry, environment_variables, [])

        names = options.artifact_filters.split(',')
        find_specs = list(filter_generator.GetFindSpecs(names))
        if not find_specs:
          continue

        find_specs_generated = True

      if find_specs:
        file_entries_generator = entry_lister.ListFileEntriesWithFindSpecs(
            [base_path_spec], find_specs)
      else:
        file_entries_generator = entry_lister.ListFileEntries([base_path_spec])

      if not bodyfile_header_printed:
        print('# extended bodyfile 3 format')
        bodyfile_header_printed = True

      bodyfile_generator = bodyfile.BodyfileGenerator()
      for file_entry, path_segments in file_entries_generator:
        for bodyfile_entry in bodyfile_generator.GetEntries(
            file_entry, path_segments):
          print(bodyfile_entry)

  except dfvfs_errors.ScannerError as exception:
    print(f'[ERROR] {exception!s}', file=sys.stderr)
    print('')
    return 1

  except KeyboardInterrupt:
    print('Aborted by user.', file=sys.stderr)
    print('')
    return 1

  if options.artifact_filters and not find_specs_generated:
    print('[ERROR] an artifact filter was specified but no corresponding '
          'file system find specifications were generated.')
    print('')
    return 1

  return 0


def MapExtents():
  """Console script to map extents.

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

  except KeyboardInterrupt:
    print('Aborted by user.', file=sys.stderr)
    return 1

  return 0


def RecursiveHasher():
  """Console script to recursive hash data streams.

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

  except KeyboardInterrupt:
    print('Aborted by user.', file=sys.stderr)
    print('')
    return 1

  return 0


def SourceAnalayzer():
  """Console script to analyze sources.

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

  except KeyboardInterrupt:
    print('Aborted by user.')
    return 1

  return 0
