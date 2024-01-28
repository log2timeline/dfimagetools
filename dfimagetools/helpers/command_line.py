# -*- coding: utf-8 -*-
"""Command line argument helper functions."""

import codecs

from dfvfs.helpers import command_line as dfvfs_command_line
from dfvfs.helpers import volume_scanner as dfvfs_volume_scanner

from dfimagetools.helpers import backend as backend_helper


SUPPORTED_CREDENTIAL_TYPES = frozenset([
    'key_data', 'password', 'recovery_password', 'startup_key'])


def AddStorageMediaImageCLIArguments(argument_parser):
  """Adds storage media image command line arguments.

  Args:
    argument_parser (argparse.ArgumentParser): argument parser.
  """
  argument_parser.add_argument(
      '--back_end', '--back-end', dest='back_end', action='store',
      metavar='NTFS', default=None, help='preferred dfVFS back-end.')

  credential_types = ', '.join(sorted(SUPPORTED_CREDENTIAL_TYPES))
  argument_parser.add_argument(
      '--credential', action='append', default=[], type=str,
      dest='credentials', metavar='TYPE:DATA', help=(
          f'Define a credentials that can be used to unlock encrypted '
          f'volumes e.g. BitLocker. A credential is defined as type:data '
          f'e.g. "password:BDE-test". Supported credential types are: '
          f'{credential_types:s}. Binary key data is expected to be passed '
          f'in BASE-16 encoding (hexadecimal). WARNING credentials passed '
          f'via command line arguments can end up in logs, so use this '
          f'option with care.'))

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


def ParseStorageMediaImageCLIArguments(options):
  """Parses storage media image command line arguments.

  Args:
    options (argparse.Namespace): command line arguments.

  Returns:
    tuple[dfvfs.CLIVolumeScannerMediator, dfvfs.VolumeScannerOptions]: dfVFS
        volume scanner mediator and options.

  Raises:
    RuntimeError: when the options are invalid.
  """
  back_end = getattr(options, 'back_end', None)
  credentials = getattr(options, 'credentials', [])
  partitions = getattr(options, 'partitions', None)
  snapshots = getattr(options, 'snapshots', None)
  volumes = getattr(options, 'volumes', None)

  backend_helper.SetDFVFSBackEnd(back_end)

  mediator = dfvfs_command_line.CLIVolumeScannerMediator()

  volume_scanner_options = dfvfs_volume_scanner.VolumeScannerOptions()

  for credential_string in credentials:
    credential_type, _, credential_data = credential_string.partition(':')
    if not credential_type or not credential_data:
      raise RuntimeError(f'Unsupported credential: {credential_string:s}.')

    if credential_type not in SUPPORTED_CREDENTIAL_TYPES:
      raise RuntimeError(
          f'Unsupported credential type for: {credential_string:s}.')

    if credential_type == 'key_data':
      try:
        credential_data = codecs.decode(credential_data, 'hex')
      except TypeError:
        raise RuntimeError(
            f'Unsupported credential data for: {credential_string:s}.')

    credential_tuple = (credential_type, credential_data)
    volume_scanner_options.credentials.append(credential_tuple)

  volume_scanner_options.partitions = mediator.ParseVolumeIdentifiersString(
      partitions)

  if snapshots == 'none':
    volume_scanner_options.snapshots = ['none']
  else:
    volume_scanner_options.snapshots = mediator.ParseVolumeIdentifiersString(
        snapshots)

  volume_scanner_options.volumes = mediator.ParseVolumeIdentifiersString(
      volumes)

  return mediator, volume_scanner_options
