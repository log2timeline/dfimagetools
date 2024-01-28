#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Helper to recursively check for volumes and file systems."""

import locale
import os

from dfvfs.credentials import manager as credentials_manager
from dfvfs.helpers import source_scanner as dfvfs_source_scanner
from dfvfs.lib import definitions as dfvfs_definitions
from dfvfs.resolver import resolver


class SourceAnalyzer(object):
  """Analyzer to recursively check for volumes and file systems."""

  # Class constant that defines the default read buffer size.
  _READ_BUFFER_SIZE = 32768

  def __init__(self, auto_recurse=True, mediator=None):
    """Initializes a source analyzer.

    Args:
      auto_recurse (Optional[bool]): True if the scan should automatically
          recurse as far as possible.
      mediator (Optional[VolumeScannerMediator]): a volume scanner mediator.
    """
    super(SourceAnalyzer, self).__init__()
    self._auto_recurse = auto_recurse
    self._encode_errors = 'strict'
    self._mediator = mediator
    self._preferred_encoding = locale.getpreferredencoding()
    self._source_scanner = dfvfs_source_scanner.SourceScanner()

  def Analyze(self, source_path):
    """Analyzes the source.

    Args:
      source_path (str): the source path.

    Yields:
      dfvfs.SourceScannerContext: the source scanner context.

    Raises:
      RuntimeError: if the source path does not exists, or if the source path
          is not a file or directory, or if the format of or within the source
          file is not supported.
    """
    if (not source_path.startswith('\\\\.\\') and
        not os.path.exists(source_path)):
      raise RuntimeError(f'No such source: {source_path:s}.')

    scan_context = dfvfs_source_scanner.SourceScannerContext()
    scan_path_spec = None

    scan_context.OpenSourcePath(source_path)

    while True:
      self._source_scanner.Scan(
          scan_context, auto_recurse=self._auto_recurse,
          scan_path_spec=scan_path_spec)

      if not scan_context.updated:
        break

      if not self._auto_recurse:
        yield scan_context

      # The source is a directory or file.
      if scan_context.source_type in (
          dfvfs_definitions.SOURCE_TYPE_DIRECTORY,
          dfvfs_definitions.SOURCE_TYPE_FILE):
        break

      # The source scanner found a locked volume, e.g. an encrypted volume,
      # and we need a credential to unlock the volume.
      for locked_scan_node in scan_context.locked_scan_nodes:
        credentials = credentials_manager.CredentialsManager.GetCredentials(
            locked_scan_node.path_spec)

        self._mediator.UnlockEncryptedVolume(
            self._source_scanner, scan_context, locked_scan_node, credentials)

      if not self._auto_recurse:
        scan_node = scan_context.GetUnscannedScanNode()
        if not scan_node:
          return
        scan_path_spec = scan_node.path_spec

    if self._auto_recurse:
      yield scan_context

  def WriteScanNode(self, scan_context, scan_node, indentation=''):
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
      self.WriteScanNode(scan_context, sub_scan_node, indentation=indentation)
