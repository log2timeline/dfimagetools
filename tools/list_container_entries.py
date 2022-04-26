#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Script to list file entries from an overlay filesystem."""

import argparse
import logging
import os
import sys
from unittest.loader import VALID_MODULE_NAME

from dfimagetools import docker
from dfvfs.helpers import command_line as dfvfs_command_line
from dfvfs.helpers import volume_scanner as dfvfs_volume_scanner
from dfvfs.lib import errors as dfvfs_errors
from dfvfs.resolver import resolver as dfvfs_resolver
from dfvfs.path import factory as dfvfs_factory


_DEFAULT_DOCKER_DIRECTORY = '/var/lib/docker'

def Main():
  """The main program function.

  Returns:
    bool: True if successful or False if not.
  """
  argument_parser = argparse.ArgumentParser(description=(
      'Lists metadata of file entries in a container on storage media image.'))

  argument_parser.add_argument(
    '--container_id', '--container-id', dest='container_id',
      action='store', type=str, default='all', help=(
          'Docker folder location.  Default is all.'))

  argument_parser.add_argument(
    '--docker_folder', '--docker-folder', dest='docker_folder',
      action='store', type=str, default=_DEFAULT_DOCKER_DIRECTORY, help=(
          'Docker folder location.  Default is /var/lib/docker'))

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
      default=None, help='path of the storage media image.')

  options = argument_parser.parse_args()

  if not options.source:
    print('Source value is missing.')
    print('')
    argument_parser.print_help()
    print('')
    return False

  logging.basicConfig(
      level=logging.INFO, format='[%(levelname)s] %(message)s')

  mediator = dfvfs_command_line.CLIVolumeScannerMediator()

  volume_scanner_options = dfvfs_volume_scanner.VolumeScannerOptions()
  volume_scanner_options.partitions = mediator.ParseVolumeIdentifiersString(
      options.partitions)

  if options.snapshots == 'none':
    volume_scanner_options.snapshots = ['none']
  else:
    volume_scanner_options.snapshots = mediator.ParseVolumeIdentifiersString(
        options.snapshots)

  volume_scanner_options.volumes = mediator.ParseVolumeIdentifiersString(
      options.volumes)

  volume_scanner = dfvfs_volume_scanner.VolumeScanner(mediator=mediator)

  try:
    base_path_specs = volume_scanner.GetBasePathSpecs(
      options.source, options=volume_scanner_options)
    if not base_path_specs:
      print('No supported file ystem found in source.')
      print('')
      return False

    for base_path_spec in base_path_specs:
      docker_path_spec = dfvfs_factory.Factory.NewPathSpec(
        base_path_spec.TYPE_INDICATOR, location=options.docker_folder,
        parent=base_path_spec.parent)

      file_system = dfvfs_resolver.Resolver.OpenFileSystem(docker_path_spec)
      if not file_system.FileEntryExistsByPathSpec(docker_path_spec):
        print('[INFO] docker folder not found.', file=sys.stderr)
        continue

      docker_instance = docker.DockerInstance(docker_path_spec)
      for container_entry in docker_instance.GetContainierEntries():
        container = docker_instance.GetContainerByIdentifier(
            container_entry.name)

        print(f'[INFO] Enumerating overlay for {container.name} '
              f'{container.identifier}.')
        fs = container.GetOverlayFileSystem()
        ListEntries(fs.GetRootFileEntry())


  except dfvfs_errors.ScannerError as exception:
    print('[ERROR] {0!s}'.format(exception), file=sys.stderr)
    print('')
    return False

  except KeyboardInterrupt:
    print('Aborted by user.', file=sys.stderr)
    print('')
    return False

  return True


def ListEntries(current_entry):
  for entry in current_entry.sub_file_entries:
    print(entry.path_spec.location, entry.path_spec.parent.location)
    if entry.IsDirectory():
      ListEntries(entry)



if __name__ == '__main__':
  if not Main():
    sys.exit(1)
  else:
    sys.exit(0)
