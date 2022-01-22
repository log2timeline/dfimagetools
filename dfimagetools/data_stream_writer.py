# -*- coding: utf-8 -*-
"""Helper to write data streams."""

import os


class DataStreamWriter(object):
  """Data stream writer."""

  _BUFFER_SIZE = 32768

  _NON_PRINTABLE_CHARACTERS = list(range(0, 0x20)) + list(range(0x7f, 0xa0))

  _ESCAPE_CHARACTERS = {
      '/': '\\/',
      ':': '\\:',
      '\\': '\\\\',
      '|': '\\|'}
  _ESCAPE_CHARACTERS.update({
      value: '\\x{0:02x}'.format(value)
      for value in _NON_PRINTABLE_CHARACTERS})

  _INVALID_PATH_CHARACTERS = [
      os.path.sep, '!', '$', '%', '&', '*', '+', ':', ';', '<', '>', '?', '@',
      '|', '~']
  _INVALID_PATH_CHARACTERS.extend(_NON_PRINTABLE_CHARACTERS)

  def __init__(self):
    """Initializes a data stream writer."""
    super(DataStreamWriter, self).__init__()
    self._display_escape_characters = str.maketrans(self._ESCAPE_CHARACTERS)
    self._invalid_path_characters = str.maketrans({
      value: '_' for value in self._INVALID_PATH_CHARACTERS})

  def GetDisplayPath(
      self, source_path_segments, source_data_stream_name):
    """Retrieves a path to display.

    Args:
      source_path_segments (list[str]): path segment of the source file.
      source_data_stream_name (str): name of the data stream of the source file.

    Returns:
      str: display path.
    """
    path_segments = [
        path_segment.translate(self._display_escape_characters)
        for path_segment in source_path_segments]

    display_path = '/'.join(path_segments)
    if source_data_stream_name:
      display_path = ':'.join([display_path, source_data_stream_name])

    return display_path

  def GetSanitizedPath(
      self, source_path_segments, source_data_stream_name, target_path):
    """Retrieves santized a path.

    This function replaces non-printable and other invalid path characters with
    an underscore "_".

    Args:
      source_path_segments (list[str]): path segment of the source file.
      source_data_stream_name (str): name of the data stream of the source file.
      target_path (str): path of the target directory.

    Returns:
      str: sanitized path.
    """
    path_segments = [
        path_segment.translate(self._invalid_path_characters)
        for path_segment in source_path_segments]

    destination_path = os.path.join(target_path, *path_segments)
    if source_data_stream_name:
      source_data_stream_name = source_data_stream_name.translate(
          self._invalid_path_characters)
      destination_path = '_'.join([destination_path, source_data_stream_name])

    return destination_path

  def WriteDataStream(self, file_entry, data_stream_name, destination_path):
    """Writes the contents of the source data stream to a destination file.

    Note that this function will overwrite an existing file.

    Args:
      file_entry (dfvfs.FileEntry): file entry whose content is to be written.
      data_stream_name (str): name of the data stream whose content is to be
          written.
      destination_path (str): path of the destination file.
    """
    source_file_object = file_entry.GetFileObject(
        data_stream_name=data_stream_name)
    if source_file_object:
      with open(destination_path, 'wb') as destination_file_object:
        source_file_object.seek(0, os.SEEK_SET)

        data = source_file_object.read(self._BUFFER_SIZE)
        while data:
          destination_file_object.write(data)
          data = source_file_object.read(self._BUFFER_SIZE)
