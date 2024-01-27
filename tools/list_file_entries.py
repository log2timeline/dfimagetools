#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Script to list file entries."""

import argparse
import logging
import os
import sys

from artifacts import reader as artifacts_reader
from artifacts import registry as artifacts_registry

from dfvfs.lib import errors as dfvfs_errors

from dfimagetools import artifact_filters
from dfimagetools import bodyfile
from dfimagetools import file_entry_lister
from dfimagetools import windows_registry
from dfimagetools.helpers import command_line


def Main():
  """The main program function.

  Returns:
    bool: True if successful or False if not.
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
    return False

  if options.output_format != 'bodyfile':
    print(f'Unsupported output format: {options.output_format:s}.')
    print('')
    argument_parser.print_help()
    print('')
    return False

  if options.artifact_filters:
    if (not options.artifact_definitions and
        not options.custom_artifact_definitions):
      print('[ERROR] artifact filters were specified but no paths to '
            'artifact definitions were provided.')
      print('')
      return False

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
      return False

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

      print('# extended bodyfile 3 format')

      bodyfile_generator = bodyfile.BodyfileGenerator()
      for file_entry, path_segments in file_entries_generator:
        for bodyfile_entry in bodyfile_generator.GetEntries(
            file_entry, path_segments):
          print(bodyfile_entry)

  except dfvfs_errors.ScannerError as exception:
    print(f'[ERROR] {exception!s}', file=sys.stderr)
    print('')
    return False

  except KeyboardInterrupt:
    print('Aborted by user.', file=sys.stderr)
    print('')
    return False

  if options.artifact_filters and not find_specs_generated:
    print('[ERROR] an artifact filter was specified but no corresponding '
          'file system find specifications were generated.')
    print('')
    return False

  return True


if __name__ == '__main__':
  if not Main():
    sys.exit(1)
  else:
    sys.exit(0)
