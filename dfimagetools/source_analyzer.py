#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Helper to recursively check for volumes and file systems."""

import locale
import os

from dfvfs.credentials import manager as credentials_manager
from dfvfs.helpers import source_scanner
from dfvfs.lib import definitions as dfvfs_definitions


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
    self._source_scanner = source_scanner.SourceScanner()

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

    scan_context = source_scanner.SourceScannerContext()
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
