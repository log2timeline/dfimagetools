# -*- coding: utf-8 -*-
"""Helper to list file entries."""

import logging
import re

from dfdatetime import definitions as dfdatetime_definitions
from dfvfs.vfs import ntfs_attribute as dfvfs_ntfs_attribute

from dfvfs.analyzer import analyzer
from dfvfs.analyzer import fvde_analyzer_helper
from dfvfs.helpers import volume_scanner
from dfvfs.lib import definitions as dfvfs_definitions
from dfvfs.resolver import resolver


try:
  # Disable experimental FVDE support.
  analyzer.Analyzer.DeregisterHelper(fvde_analyzer_helper.FVDEAnalyzerHelper())
except KeyError:
  pass


class FileEntryLister(volume_scanner.VolumeScanner):
  """File entry lister."""

  _NON_PRINTABLE_CHARACTERS = list(range(0, 0x20)) + list(range(0x7f, 0xa0))

  _BODYFILE_ESCAPE_CHARACTERS = {
      '/': '\\/',
      ':': '\\:',
      '\\': '\\\\',
      '|': '\\|'}
  _BODYFILE_ESCAPE_CHARACTERS.update({
      value: '\\x{0:02x}'.format(value)
      for value in _NON_PRINTABLE_CHARACTERS})

  _FILE_TYPES = {
      0x1000: 'p',
      0x2000: 'c',
      0x4000: 'd',
      0x6000: 'b',
      0xa000: 'l',
      0xc000: 's'}

  _TIMESTAMP_FORMAT_STRINGS = {
      dfdatetime_definitions.PRECISION_1_NANOSECOND: '{0:d}.{1:09d}',
      dfdatetime_definitions.PRECISION_100_NANOSECONDS: '{0:d}.{1:07d}',
      dfdatetime_definitions.PRECISION_1_MICROSECOND: '{0:d}.{1:06d}',
      dfdatetime_definitions.PRECISION_1_MILLISECOND: '{0:d}.{1:03d}'}

  _UNICODE_SURROGATES_RE = re.compile('[\ud800-\udfff]')

  def __init__(self, mediator=None):
    """Initializes a file entry lister.

    Args:
      mediator (dfvfs.VolumeScannerMediator): a volume scanner mediator.
    """
    super(FileEntryLister, self).__init__(mediator=mediator)
    self._bodyfile_escape_characters = str.maketrans(
        self._BODYFILE_ESCAPE_CHARACTERS)
    self._list_only_files = False

  def _GetBodyfileModeString(self, mode):
    """Retrieves a bodyfile string representation of a mode.

    Args:
      mode (int): mode.

    Returns:
      str: bodyfile string representation of the mode.
    """
    file_mode = 10 * ['-']

    if mode & 0x0001:
      file_mode[9] = 'x'
    if mode & 0x0002:
      file_mode[8] = 'w'
    if mode & 0x0004:
      file_mode[7] = 'r'

    if mode & 0x0008:
      file_mode[6] = 'x'
    if mode & 0x0010:
      file_mode[5] = 'w'
    if mode & 0x0020:
      file_mode[4] = 'r'

    if mode & 0x0040:
      file_mode[3] = 'x'
    if mode & 0x0080:
      file_mode[2] = 'w'
    if mode & 0x0100:
      file_mode[1] = 'r'

    file_mode[0] = self._FILE_TYPES.get(mode & 0xf000, '-')

    return ''.join(file_mode)

  def _GetBodyfileName(self, path_spec, path_segments):
    """Retrieves a bodyfile name value.

    Args:
      path_spec (dfvfs.PathSpec): path specification of the file entry.
      path_segments (list[str]): path segments of the full path of the file
          entry.

    Returns:
      str: bodyfile name value.
    """
    name_value = ''

    if path_spec.HasParent():
      parent_path_spec = path_spec.parent
      if parent_path_spec and parent_path_spec.type_indicator in (
          dfvfs_definitions.PARTITION_TABLE_TYPE_INDICATORS):
        name_value = ''.join([name_value, parent_path_spec.location])

    path_segments = [
        segment.translate(self._bodyfile_escape_characters)
        for segment in path_segments]
    name_value = ''.join([name_value, '/'.join(path_segments)])

    return name_value or '/'

  def _GetBodyfileTimestamp(self, date_time):
    """Retrieves a bodyfile timestamp representation of a date time value.

    Args:
      date_time (dfdatetime.DateTimeValues): date time value.

    Returns:
      str: bodyfile timestamp representation of the date time value.
    """
    if not date_time:
      return ''

    posix_timestamp, fraction_of_second = (
        date_time.CopyToPosixTimestampWithFractionOfSecond())
    format_string = self._TIMESTAMP_FORMAT_STRINGS.get(
        date_time.precision, '{0:d}')
    return format_string.format(posix_timestamp, fraction_of_second)

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
    path_segments = parent_path_segments + [file_entry.name]

    if not self._list_only_files or file_entry.IsFile():
      yield file_entry, path_segments

    for sub_file_entry in file_entry.sub_file_entries:
      for result in self._ListFileEntry(
          file_system, sub_file_entry, path_segments):
        yield result

  def GetBodyfileEntries(self, file_entry, path_segments):
    """Retrieves bodyfile entry representations of a file entry.

    Args:
      file_entry (dfvfs.FileEntry): file entry.
      path_segments (str): path segments of the full path of the file entry.

    Yields:
      str: bodyfile entry.
    """
    stat_attribute = file_entry.GetStatAttribute()

    if stat_attribute.inode_number is None:
      inode_string = ''
    elif file_entry.type_indicator == dfvfs_definitions.TYPE_INDICATOR_NTFS:
      inode_string = '{0:d}-{1:d}'.format(
          stat_attribute.inode_number & 0xffffffffffff,
          stat_attribute.inode_number >> 48)
    else:
      inode_string = '{0:d}'.format(stat_attribute.inode_number)

    mode = getattr(stat_attribute, 'mode', None) or 0
    mode_string = self._GetBodyfileModeString(mode)

    owner_identifier = ''
    if stat_attribute.owner_identifier is not None:
      owner_identifier = str(stat_attribute.owner_identifier)

    group_identifier = ''
    if stat_attribute.group_identifier is not None:
      group_identifier = str(stat_attribute.group_identifier)

    size = str(file_entry.size)

    access_time = self._GetBodyfileTimestamp(file_entry.access_time)
    creation_time = self._GetBodyfileTimestamp(file_entry.creation_time)
    change_time = self._GetBodyfileTimestamp(file_entry.change_time)
    modification_time = self._GetBodyfileTimestamp(file_entry.modification_time)

    # TODO: add support to calculate MD5
    md5_string = '0'

    file_entry_name_value = self._GetBodyfileName(
        file_entry.path_spec, path_segments)

    yield '|'.join([
        md5_string, file_entry_name_value, inode_string, mode_string,
        owner_identifier, group_identifier, size, access_time,
        modification_time, change_time, creation_time])

    for data_stream in file_entry.data_streams:
      if data_stream.name:
        data_stream_name = data_stream.name.translate(
            self._bodyfile_escape_characters)
        data_stream_name_value = ':'.join([
            file_entry_name_value, data_stream_name])

        yield '|'.join([
            md5_string, data_stream_name_value, inode_string, mode_string,
            owner_identifier, group_identifier, size, access_time,
            modification_time, change_time, creation_time])

    for attribute in file_entry.attributes:
      if isinstance(attribute, dfvfs_ntfs_attribute.FileNameNTFSAttribute):
        if attribute.name == file_entry.name:
          attribute_name_value = '{0:s} ($FILE_NAME)'.format(
              file_entry_name_value)

          access_time = self._GetBodyfileTimestamp(attribute.access_time)
          creation_time = self._GetBodyfileTimestamp(attribute.creation_time)
          change_time = self._GetBodyfileTimestamp(
              attribute.entry_modification_time)
          modification_time = self._GetBodyfileTimestamp(
              attribute.modification_time)

          yield '|'.join([
              md5_string, attribute_name_value, inode_string, mode_string,
              owner_identifier, group_identifier, size, access_time,
              modification_time, change_time, creation_time])

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

      for result in self._ListFileEntry(file_system, file_entry, []):
        yield result
