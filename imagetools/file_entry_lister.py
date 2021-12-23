# -*- coding: utf-8 -*-
"""Helper to list file entries."""

import logging

from dfdatetime import definitions as dfdatetime_definitions

from dfvfs.analyzer import analyzer
from dfvfs.analyzer import fvde_analyzer_helper
from dfvfs.helpers import volume_scanner
from dfvfs.lib import definitions as dfvfs_definitions
from dfvfs.resolver import resolver
from dfvfs.vfs import attribute as dfvfs_attribute

from imagetools import helpers


try:
  # Disable experimental FVDE support.
  analyzer.Analyzer.DeregisterHelper(fvde_analyzer_helper.FVDEAnalyzerHelper())
except KeyError:
  pass


class FileEntryLister(volume_scanner.VolumeScanner):
  """File entry lister."""

  _NON_PRINTABLE_CHARACTERS = list(range(0, 0x20)) + list(range(0x7f, 0xa0))
  _ESCAPE_CHARACTERS = str.maketrans({
      value: '\\x{0:02x}'.format(value)
      for value in _NON_PRINTABLE_CHARACTERS})

  _MODE_TYPE = {
      0x1000: 'p',
      0x2000: 'c',
      0x4000: 'd',
      0x6000: 'b',
      0xa000: 'l',
      0xc000: 's'}


  _TIMESTAMP_FORMAT_STRINGS = {
      dfdatetime_definitions.PRECISION_1_NANOSECOND: '{0:.9f}',
      dfdatetime_definitions.PRECISION_100_NANOSECONDS: '{0:.7f}',
      dfdatetime_definitions.PRECISION_1_MICROSECOND: '{0:.6f}',
      dfdatetime_definitions.PRECISION_1_MILLISECOND: '{0:.3f}'}

  def __init__(self, mediator=None):
    """Initializes a file entry lister.

    Args:
      mediator (dfvfs.VolumeScannerMediator): a volume scanner mediator.
    """
    super(FileEntryLister, self).__init__(mediator=mediator)
    self._list_only_files = False

  def _GetDisplayPath(self, path_spec, path_segments, data_stream_name):
    """Retrieves a path to display.

    Args:
      path_spec (dfvfs.PathSpec): path specification of the file entry.
      path_segments (list[str]): path segments of the full path of the file
          entry.
      data_stream_name (str): name of the data stream.

    Returns:
      str: path to display.
    """
    display_path = ''

    if path_spec.HasParent():
      parent_path_spec = path_spec.parent
      if parent_path_spec and parent_path_spec.type_indicator == (
          dfvfs_definitions.TYPE_INDICATOR_TSK_PARTITION):
        display_path = ''.join([display_path, parent_path_spec.location])

    path_segments = [
        segment.translate(self._ESCAPE_CHARACTERS) for segment in path_segments]
    display_path = ''.join([display_path, '/'.join(path_segments)])

    if data_stream_name:
      data_stream_name = data_stream_name.translate(self._ESCAPE_CHARACTERS)
      display_path = ':'.join([display_path, data_stream_name])

    return display_path or '/'

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

    file_mode[0] = self._MODE_TYPE.get(mode & 0xf000, '-')

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

    posix_timestamp = date_time.CopyToPosixTimestampWithFractionOfSecond()
    format_string = self._TIMESTAMP_FORMAT_STRINGS.get(
        date_time.precision, '{0:.0f}')
    return format_string.format(posix_timestamp)

  def _ListFileEntry(self, file_system, file_entry, parent_path_segments):
    """Lists a file entry.

    Args:
      file_system (dfvfs.FileSystem): file system that contains the file entry.
      file_entry (dfvfs.FileEntry): file entry to list.
      parent_path_segments (str): path segments of the full path of the parent
          file entry.

    Yields:
      tuple[str, dfvfs.FileEntry]: display name and file entry.
    """
    path_segments = parent_path_segments + [file_entry.name]

    display_path = self._GetDisplayPath(file_entry.path_spec, path_segments, '')
    if not self._list_only_files or file_entry.IsFile():
      yield display_path, file_entry

    # TODO: print data stream names.

    for sub_file_entry in file_entry.sub_file_entries:
      for entry in self._ListFileEntry(
          file_system, sub_file_entry, path_segments):
        yield entry

  def GetBodyfileEntry(self, path, file_entry):
    """Retrieves a bodyfile entry representation of the file entry.

    Args:
      path (str): display name.
      file_entry (dfvfs.FileEntry): file entry.

    Returns:
      str: bodyfile entry.
    """
    stat_attribute = None
    for attribute in file_entry.attributes:
      if isinstance(attribute, dfvfs_attribute.StatAttribute):
        stat_attribute = attribute
        break

    # TODO: add support to calculate MD5
    md5_string = '0'

    inode_number = str(getattr(stat_attribute, 'inode_number', ''))

    mode = getattr(stat_attribute, 'mode', 0)
    mode_string = self._GetBodyfileModeString(mode)

    owner_identifier = str(getattr(stat_attribute, 'owner_identifier', ''))
    group_identifier = str(getattr(stat_attribute, 'group_identifier', ''))
    size = str(file_entry.size)

    access_time = self._GetBodyfileTimestamp(file_entry.access_time)
    creation_time = self._GetBodyfileTimestamp(file_entry.creation_time)
    change_time = self._GetBodyfileTimestamp(file_entry.change_time)
    modification_time = self._GetBodyfileTimestamp(file_entry.modification_time)

    # Colums in a Sleuthkit 3.x and later bodyfile
    # MD5|name|inode|mode_as_string|UID|GID|size|atime|mtime|ctime|crtime
    return '|'.join([
        md5_string, path, inode_number, mode_string, owner_identifier,
        group_identifier, size, access_time, modification_time, change_time,
        creation_time])

  def ListFileEntries(self, base_path_specs):
    """Lists file entries in the base path specification.

    Args:
      base_path_specs (list[dfvfs.PathSpec]): source path specification.

    Yields:
      tuple[str, dfvfs.FileEntry]: display name and file entry.
    """
    for base_path_spec in base_path_specs:
      file_system = resolver.Resolver.OpenFileSystem(base_path_spec)
      file_entry = resolver.Resolver.OpenFileEntry(base_path_spec)
      if file_entry is None:
        path_specification_string = helpers.GetPathSpecificationString(
            base_path_spec)
        logging.warning(
            'Unable to open base path specification:\n{0:s}'.format(
                path_specification_string))
        return

      for entry in self._ListFileEntry(file_system, file_entry, []):
        yield entry
