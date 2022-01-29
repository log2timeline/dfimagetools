# -*- coding: utf-8 -*-
"""Helper to list file entries."""

import logging
import re

from dfvfs.helpers import file_system_searcher
from dfvfs.helpers import volume_scanner
from dfvfs.helpers import windows_path_resolver
from dfvfs.lib import definitions as dfvfs_definitions
from dfvfs.path import factory as dfvfs_path_spec_factory
from dfvfs.resolver import resolver as dfvfs_resolver
from dfvfs.volume import factory as dfvfs_volume_system_factory

from dfimagetools import bodyfile
from dfimagetools import decorators


class FileEntryLister(volume_scanner.VolumeScanner):
  """File entry lister."""

  _UNICODE_SURROGATES_RE = re.compile('[\ud800-\udfff]')

  _WINDOWS_DIRECTORIES = frozenset([
      'C:\\Windows',
      'C:\\WINNT',
      'C:\\WTSRV',
      'C:\\WINNT35',
  ])

  def __init__(self, mediator=None):
    """Initializes a file entry lister.

    Args:
      mediator (dfvfs.VolumeScannerMediator): a volume scanner mediator.
    """
    super(FileEntryLister, self).__init__(mediator=mediator)
    self._bodyfile_generator = bodyfile.BodyfileGenerator()
    self._list_only_files = False

  def _GetBasePathSegments(self, base_path_spec):
    """Retrieves the base path segments.

    Args:
      base_path_specs (list[dfvfs.PathSpec]): source path specification.

    Returns:
      list[str]: path segments.
    """
    if not base_path_spec.HasParent() or not base_path_spec.parent:
      return ['']

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

      volume_path_segment = '{0:s}{{{1:s}}}'.format(
          volume_identifier_prefix, volume_identifier.value)
      return ['', volume_path_segment]

    if base_path_spec.parent.type_indicator == (
        dfvfs_definitions.TYPE_INDICATOR_TSK_PARTITION):
      return base_path_spec.parent.location.split('/')

    return ['']

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

  def GetWindowsDirectory(self, base_path_spec):
    """Retrieves the Windows directory from the base path specification.

    Args:
      base_path_spec (dfvfs.PathSpec): source path specification.

    Returns:
      str: path of the Windows directory or None if not available.
    """
    if base_path_spec.type_indicator == dfvfs_definitions.TYPE_INDICATOR_OS:
      mount_point = base_path_spec
    else:
      mount_point = base_path_spec.parent

    file_system = dfvfs_resolver.Resolver.OpenFileSystem(base_path_spec)
    path_resolver = windows_path_resolver.WindowsPathResolver(
        file_system, mount_point)

    for windows_path in self._WINDOWS_DIRECTORIES:
      windows_path_spec = path_resolver.ResolvePath(windows_path)
      if windows_path_spec is not None:
        return windows_path

    return None

  def ListFileEntries(self, base_path_specs):
    """Lists file entries in the base path specifications.

    Args:
      base_path_specs (list[dfvfs.PathSpec]): source path specifications.

    Yields:
      tuple[dfvfs.FileEntry, list[str]]: file entry and path segments.
    """
    for base_path_spec in base_path_specs:
      file_system = dfvfs_resolver.Resolver.OpenFileSystem(base_path_spec)
      file_entry = dfvfs_resolver.Resolver.OpenFileEntry(base_path_spec)
      if file_entry is None:
        path_specification_string = self._GetPathSpecificationString(
            base_path_spec)
        logging.warning('Unable to open base path specification:\n{0:s}'.format(
            path_specification_string))
        return

      base_path_segments = self._GetBasePathSegments(base_path_spec)
      for result in self._ListFileEntry(
          file_system, file_entry, base_path_segments):
        yield result

  def ListFileEntriesWithFindSpecs(self, base_path_specs, find_specs):
    """Lists file entries in the base path specifications.

    This method filters file entries based on the find specifications.

    Args:
      base_path_specs (list[dfvfs.PathSpec]): source path specification.
      find_specs (list[dfvfs.FindSpec]): find specifications.

    Yields:
      tuple[dfvfs.FileEntry, list[str]]: file entry and path segments.
    """
    for base_path_spec in base_path_specs:
      file_system = dfvfs_resolver.Resolver.OpenFileSystem(base_path_spec)

      if dfvfs_path_spec_factory.Factory.IsSystemLevelTypeIndicator(
          base_path_spec.type_indicator):
        mount_point = base_path_spec
      else:
        mount_point = base_path_spec.parent

      base_path_segments = self._GetBasePathSegments(base_path_spec)

      searcher = file_system_searcher.FileSystemSearcher(
          file_system, mount_point)
      for path_spec in searcher.Find(find_specs=find_specs):
        file_entry = dfvfs_resolver.Resolver.OpenFileEntry(path_spec)
        path_segments = file_system.SplitPath(path_spec.location)

        full_path_segments = list(base_path_segments)
        full_path_segments.extend(path_segments)
        yield file_entry, full_path_segments
