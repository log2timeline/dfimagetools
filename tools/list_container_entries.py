#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Script to list file entries from an overlay filesystem."""

import argparse
import logging
import sys

from dfimagetools import docker
from dfvfs.helpers import command_line as dfvfs_command_line
from dfvfs.helpers import volume_scanner as dfvfs_volume_scanner
from dfvfs.lib import errors as dfvfs_errors
from dfvfs.resolver import resolver as dfvfs_resolver
from dfvfs.path import factory as dfvfs_factory

from dfimagetools import bodyfile


_DEFAULT_DOCKER_DIRECTORY = '/var/lib/docker'


def _ListEntries(current_entry, bodyfile_generator, parent_path_segments):
  """Recursively print the bodyfile of a FileEntry.

  Args:
    current_entry (file_entry.FileEntry): the file entry to list bodyfile
        entries.
    bodyfile_generator (bodyfile.BodyFileGenerator): a generator for
        bodyfile entries.
    parent_path_segments (List[str]): path segments of the full path of the
        parent file entry
  """
  for entry in current_entry.sub_file_entries:
    for bodyfile_entry in bodyfile_generator.GetEntries(
        entry, parent_path_segments + [entry.name]):
      print(bodyfile_entry)
    if entry.IsDirectory():
      _ListEntries(entry, bodyfile_generator, parent_path_segments +
                   [entry.name])


def ProcessContainer(container: docker.DockerContainer):
  """Produces a bodyfile output of the container filesystem.

  Args:
    container (docker.DockerContainer): the Docker container to process.
  """
  bodyfile_generator = bodyfile.BodyfileGenerator()

  print(f'[INFO] Enumerating overlay for {container.name} '
        f'{container.identifier}.', file=sys.stderr)

  filesystem = container.GetOverlayFileSystem()
  filesystem.Open()
  _ListEntries(filesystem.GetRootFileEntry(), bodyfile_generator, [''])


def Main():
  """The main program function.

  Returns:
    bool: True if successful or False if not.
  """
  argument_parser = argparse.ArgumentParser(description=(
      'Lists metadata of file entries in a container on storage media image.'))

  argument_parser.add_argument(
      '--container_id', '--container-id', dest='container_id',
      action='store', type=str, required=True, help=(
          'Docker folder location.'))

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
      print('No supported file system found in source.')
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

      container = docker_instance.GetContainerByIdentifier(
          options.container_id)
      ProcessContainer(container)

  except dfvfs_errors.ScannerError as exception:
    print('[ERROR] {0!s}'.format(exception), file=sys.stderr)
    print('')
    return False

  except KeyboardInterrupt:
    print('Aborted by user.', file=sys.stderr)
    print('')
    return False

  return True


if __name__ == '__main__':
  if not Main():
    sys.exit(1)
  else:
    sys.exit(0)
