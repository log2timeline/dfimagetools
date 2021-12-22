# -*- coding: utf-8 -*-
"""Helper functions for CLI tools."""

import re

from dfvfs.lib import definitions as dfvfs_definitions


_UNICODE_SURROGATES_RE = re.compile('[\ud800-\udfff]')


def GetPathSpecificationString(path_spec):
  """Retrieves a printable string representation of the path specification.

  Args:
    path_spec (dfvfs.PathSpec): path specification.

  Returns:
    str: printable string representation of the path specification.
  """
  path_spec_string = path_spec.comparable

  if _UNICODE_SURROGATES_RE.search(path_spec_string):
    path_spec_string = path_spec_string.encode(
        'utf-8', errors='surrogateescape')
    path_spec_string = path_spec_string.decode(
        'utf-8', errors='backslashreplace')

  return path_spec_string


def SetDFVFSBackEnd(back_end):
  """Sets the dfVFS back-end.

  Args:
    back_end (str): dfVFS back-end.
  """
  if back_end == 'EXT':
    dfvfs_definitions.PREFERRED_EXT_BACK_END = (
        dfvfs_definitions.TYPE_INDICATOR_EXT)

  elif back_end == 'GPT':
    dfvfs_definitions.PREFERRED_GPT_BACK_END = (
        dfvfs_definitions.TYPE_INDICATOR_GPT)

  elif back_end == 'HFS':
    dfvfs_definitions.PREFERRED_HFS_BACK_END = (
        dfvfs_definitions.TYPE_INDICATOR_HFS)

  elif back_end == 'NTFS':
    dfvfs_definitions.PREFERRED_NTFS_BACK_END = (
        dfvfs_definitions.TYPE_INDICATOR_NTFS)

  elif back_end == 'TSK':
    dfvfs_definitions.PREFERRED_EXT_BACK_END = (
        dfvfs_definitions.TYPE_INDICATOR_TSK)
    dfvfs_definitions.PREFERRED_GPT_BACK_END = (
        dfvfs_definitions.TYPE_INDICATOR_TSK_PARTITION)
    dfvfs_definitions.PREFERRED_HFS_BACK_END = (
        dfvfs_definitions.TYPE_INDICATOR_TSK)
    dfvfs_definitions.PREFERRED_NTFS_BACK_END = (
        dfvfs_definitions.TYPE_INDICATOR_TSK)
