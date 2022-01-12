# -*- coding: utf-8 -*-
"""Helper to list file entries."""

import logging
import re

from dfvfs.analyzer import analyzer
from dfvfs.analyzer import fvde_analyzer_helper
from dfvfs.helpers import volume_scanner
from dfvfs.lib import definitions as dfvfs_definitions
from dfvfs.resolver import resolver
from dfvfs.volume import factory as dfvfs_volume_system_factory

from dfimagetools import bodyfile
from dfimagetools import decorators


try:
  # Disable experimental FVDE support.
  analyzer.Analyzer.DeregisterHelper(fvde_analyzer_helper.FVDEAnalyzerHelper())
except KeyError:
  pass


class FileEntryLister(volume_scanner.VolumeScanner):
  """File entry lister."""

  _UNICODE_SURROGATES_RE = re.compile('[\ud800-\udfff]')

  def __init__(self, mediator=None):
    """Initializes a file entry lister.

    Args:
      mediator (dfvfs.VolumeScannerMediator): a volume scanner mediator.
    """
    super(FileEntryLister, self).__init__(mediator=mediator)
    self._bodyfile_generator = bodyfile.BodyfileGenerator()
    self._list_only_files = False

  def _GetPathSpecificationString(self, path_spec):
    """Retrieves a printable string representation of the path specification.

    Args:
      path_spec (dfvfs.PathSpec): path specification.

    Returns:
      str: printable string representation of the path specification.
    """
    path_spec_string = path_spec.comparable

    if self._UNICODE_SURROGATES_RE.search(path_spec_string):
      path_spec_string = path_spec_string.encode(
          'utf-8', errors='surrogateescape')
      path_spec_string = path_spec_string.decode(
          'utf-8', errors='backslashreplace')

    return path_spec_string

  def _ListFileEntry(self, file_system, file_entry, parent_path_segments):
    """Lists a file entry.

    Args:
      file_system (dfvfs.FileSystem): file system that contains the file entry.
      file_entry (dfvfs.FileEntry): file entry to list.
      parent_path_segments (str): path segments of the full path of the parent
          file entry.

    Yields:
      tuple[dfvfs.FileEntry, list[str]]: file entry and path segments.
    """
    path_segments = list(parent_path_segments)
    if not file_entry.IsRoot():
      path_segments.append(file_entry.name)

    if not self._list_only_files or file_entry.IsFile():
      yield file_entry, path_segments

    for sub_file_entry in file_entry.sub_file_entries:
      for result in self._ListFileEntry(
          file_system, sub_file_entry, path_segments):
        yield result

  @decorators.deprecated
  def GetBodyfileEntries(self, file_entry, path_segments):
    """Retrieves bodyfile entry representations of a file entry.

    Args:
      file_entry (dfvfs.FileEntry): file entry.
      path_segments (str): path segments of the full path of the file entry.

    Returns:
      generator[str]: bodyfile entry generator.
    """
    return self._bodyfile_generator.GetEntries(file_entry, path_segments)

  def ListFileEntries(self, base_path_specs):
    """Lists file entries in the base path specification.

    Args:
      base_path_specs (list[dfvfs.PathSpec]): source path specification.

    Yields:
      tuple[dfvfs.FileEntry, list[str]]: file entry and path segments.
    """
    for base_path_spec in base_path_specs:
      file_system = resolver.Resolver.OpenFileSystem(base_path_spec)
      file_entry = resolver.Resolver.OpenFileEntry(base_path_spec)
      if file_entry is None:
        path_specification_string = self._GetPathSpecificationString(
            base_path_spec)
        logging.warning('Unable to open base path specification:\n{0:s}'.format(
            path_specification_string))
        return

      base_path_segments = ['']
      if base_path_spec.HasParent() and base_path_spec.parent:
        if base_path_spec.parent.type_indicator in (
            dfvfs_definitions.TYPE_INDICATOR_APFS_CONTAINER,
            dfvfs_definitions.TYPE_INDICATOR_GPT,
            dfvfs_definitions.TYPE_INDICATOR_LVM):
          volume_system = dfvfs_volume_system_factory.Factory.NewVolumeSystem(
              base_path_spec.parent.type_indicator)
          volume_system.Open(base_path_spec.parent)

          volume = volume_system.GetVolumeByIdentifier(
              base_path_spec.parent.location[1:])

          if base_path_spec.parent.type_indicator == (
              dfvfs_definitions.TYPE_INDICATOR_GPT):
            volume_identifier_prefix = 'gpt'
          else:
            volume_identifier_prefix = volume_system.VOLUME_IDENTIFIER_PREFIX

          volume_identifier = volume.GetAttribute('identifier')

          base_path_segments = ['', '{0:s}{{{1:s}}}'.format(
              volume_identifier_prefix, volume_identifier.value)]

        elif base_path_spec.parent.type_indicator == (
            dfvfs_definitions.TYPE_INDICATOR_TSK_PARTITION):
          base_path_segments = base_path_spec.parent.location.split('/')

      for result in self._ListFileEntry(
          file_system, file_entry, base_path_segments):
        yield result
