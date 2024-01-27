# -*- coding: utf-8 -*-
"""dfVFS backend helper functions."""

from dfvfs.lib import definitions as dfvfs_definitions


def SetDFVFSBackEnd(back_end):
  """Sets the dfVFS back-end.

  Args:
    back_end (str): dfVFS back-end.
  """
  if back_end == 'APM':
    dfvfs_definitions.PREFERRED_APM_BACK_END = (
        dfvfs_definitions.TYPE_INDICATOR_APM)

  elif back_end == 'EXT':
    dfvfs_definitions.PREFERRED_EXT_BACK_END = (
        dfvfs_definitions.TYPE_INDICATOR_EXT)

  elif back_end == 'FAT':
    dfvfs_definitions.PREFERRED_FAT_BACK_END = (
        dfvfs_definitions.TYPE_INDICATOR_FAT)

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
    dfvfs_definitions.PREFERRED_APM_BACK_END = (
        dfvfs_definitions.TYPE_INDICATOR_TSK)
    dfvfs_definitions.PREFERRED_APM_BACK_END = (
        dfvfs_definitions.TYPE_INDICATOR_TSK)
    dfvfs_definitions.PREFERRED_FAT_BACK_END = (
        dfvfs_definitions.TYPE_INDICATOR_TSK)
    dfvfs_definitions.PREFERRED_GPT_BACK_END = (
        dfvfs_definitions.TYPE_INDICATOR_TSK_PARTITION)
    dfvfs_definitions.PREFERRED_HFS_BACK_END = (
        dfvfs_definitions.TYPE_INDICATOR_TSK)
    dfvfs_definitions.PREFERRED_NTFS_BACK_END = (
        dfvfs_definitions.TYPE_INDICATOR_TSK)
