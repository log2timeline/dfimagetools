# -*- coding: utf-8 -*-
"""Helper for generating bodyfile entries."""

from dfdatetime import definitions as dfdatetime_definitions

from dfvfs.lib import definitions as dfvfs_definitions
from dfvfs.vfs import ntfs_attribute as dfvfs_ntfs_attribute


class BodyfileGenerator(object):
  """Bodyfile generator."""

  _NON_PRINTABLE_CHARACTERS = list(range(0, 0x20)) + list(range(0x7f, 0xa0))

  _ESCAPE_CHARACTERS = {
      '/': '\\/',
      ':': '\\:',
      '\\': '\\\\',
      '|': '\\|'}
  _ESCAPE_CHARACTERS.update({
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

  def __init__(self):
    """Initializes a bodyfile generator."""
    super(BodyfileGenerator, self).__init__()
    self._bodyfile_escape_characters = str.maketrans(self._ESCAPE_CHARACTERS)

  def _GetFileAttributeFlagsString(self, file_type, file_attribute_flags):
    """Retrieves a bodyfile string representation of file attributes flags.

    Args:
      file_type (str): bodyfile file type identifier.
      file_attribute_flags (int): file attribute flags.

    Returns:
      str: bodyfile representation of the file attributes flags.
    """
    string_parts = [file_type, 'r', '-', 'x', 'r', '-', 'x', 'r', '-', 'x']

    if (not file_attribute_flags & self._FILE_ATTRIBUTE_READONLY and
        not file_attribute_flags & self._FILE_ATTRIBUTE_SYSTEM):
      string_parts[2] = 'w'
      string_parts[5] = 'w'
      string_parts[8] = 'w'

    return ''.join(string_parts)

  def _GetModeString(self, mode):
    """Retrieves a bodyfile string representation of a mode.

    Args:
      mode (int): mode.

    Returns:
      str: bodyfile representation of the mode.
    """
    string_parts = 10 * ['-']

    if mode & 0x0001:
      string_parts[9] = 'x'
    if mode & 0x0002:
      string_parts[8] = 'w'
    if mode & 0x0004:
      string_parts[7] = 'r'

    if mode & 0x0008:
      string_parts[6] = 'x'
    if mode & 0x0010:
      string_parts[5] = 'w'
    if mode & 0x0020:
      string_parts[4] = 'r'

    if mode & 0x0040:
      string_parts[3] = 'x'
    if mode & 0x0080:
      string_parts[2] = 'w'
    if mode & 0x0100:
      string_parts[1] = 'r'

    string_parts[0] = self._FILE_TYPES.get(mode & 0xf000, '-')

    return ''.join(string_parts)

  def _GetTimestamp(self, date_time):
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

  def GetEntries(self, file_entry, path_segments):
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
      mode_string = self._GetModeString(mode)

    else:
      if file_entry.entry_type == dfvfs_definitions.FILE_ENTRY_TYPE_DIRECTORY:
        file_type = 'd'
      elif file_entry.entry_type == dfvfs_definitions.FILE_ENTRY_TYPE_LINK:
        file_type = 'l'
      else:
        file_type = '-'

      if file_attribute_flags is None:
        mode_string = ''.join([file_type] + (9 * ['-']))
      else:
        mode_string = self._GetFileAttributeFlagsString(
            file_type, file_attribute_flags)

    owner_identifier = ''
    if stat_attribute.owner_identifier is not None:
      owner_identifier = str(stat_attribute.owner_identifier)

    group_identifier = ''
    if stat_attribute.group_identifier is not None:
      group_identifier = str(stat_attribute.group_identifier)

    size = str(file_entry.size)

    access_time = self._GetTimestamp(file_entry.access_time)
    creation_time = self._GetTimestamp(file_entry.creation_time)
    change_time = self._GetTimestamp(file_entry.change_time)
    modification_time = self._GetTimestamp(file_entry.modification_time)

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

          access_time = self._GetTimestamp(attribute.access_time)
          creation_time = self._GetTimestamp(attribute.creation_time)
          change_time = self._GetTimestamp(attribute.entry_modification_time)
          modification_time = self._GetTimestamp(attribute.modification_time)

          yield '|'.join([
              md5_string, attribute_name_value, inode_string, mode_string,
              owner_identifier, group_identifier, size, access_time,
              modification_time, change_time, creation_time])
