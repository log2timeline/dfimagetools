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
from dfvfs.volume import factory as dfvfs_volume_system_factory


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

  _FILE_ATTRIBUTE_READONLY = 1
  _FILE_ATTRIBUTE_SYSTEM = 4

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
    path_segments = list(parent_path_segments)
    if not file_entry.IsRoot():
      path_segments.append(file_entry.name)

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
    file_attribute_flags = None
    parent_file_reference = None
    if file_entry.type_indicator == dfvfs_definitions.TYPE_INDICATOR_NTFS:
      mft_attribute_index = getattr(file_entry.path_spec, 'mft_attribute', None)
      if mft_attribute_index is not None:
        fsntfs_file_entry = file_entry.GetNTFSFileEntry()
        file_attribute_flags = fsntfs_file_entry.file_attribute_flags
        parent_file_reference = (
            fsntfs_file_entry.get_parent_file_reference_by_attribute_index(
                mft_attribute_index))

    stat_attribute = file_entry.GetStatAttribute()

    if stat_attribute.inode_number is None:
      inode_string = ''
    elif file_entry.type_indicator == dfvfs_definitions.TYPE_INDICATOR_NTFS:
      inode_string = '{0:d}-{1:d}'.format(
          stat_attribute.inode_number & 0xffffffffffff,
          stat_attribute.inode_number >> 48)
    else:
      inode_string = '{0:d}'.format(stat_attribute.inode_number)

    if file_entry.type_indicator != dfvfs_definitions.TYPE_INDICATOR_NTFS:
      mode = getattr(stat_attribute, 'mode', None) or 0
      mode_string = self._GetBodyfileModeString(mode)

    elif file_attribute_flags is None:
      mode_string = '---------'

    elif (file_attribute_flags & self._FILE_ATTRIBUTE_READONLY or
          file_attribute_flags & self._FILE_ATTRIBUTE_SYSTEM):
      mode_string = 'r-xr-xr-x'

    else:
      mode_string = 'rwxrwxrwx'

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

    path_segments = [
        segment.translate(self._bodyfile_escape_characters)
        for segment in path_segments]
    file_entry_name_value = '/'.join(path_segments) or '/'

    if file_entry.link:
      file_entry_link = file_entry.link.translate(
          self._bodyfile_escape_characters)
      name_value = '{0:s} -> {1:s}'.format(
          file_entry_name_value, file_entry_link)
    else:
      name_value = file_entry_name_value

    yield '|'.join([
        md5_string, name_value, inode_string, mode_string, owner_identifier,
        group_identifier, size, access_time, modification_time, change_time,
        creation_time])

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
        if (attribute.name == file_entry.name and
            attribute.parent_file_reference == parent_file_reference):
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
