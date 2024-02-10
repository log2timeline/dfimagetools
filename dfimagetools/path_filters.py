# -*- coding: utf-8 -*-
"""Helper for filtering based on a path."""

import re

from dfvfs.helpers import file_system_searcher as dfvfs_file_system_searcher


class PathFiltersGenerator(object):
  """Generator of filters based on a path."""

  _PARTITION_REGEX = re.compile(r'^p[1-9][0-9]*$')

  def __init__(self, path):
    """Initializes a path filters generator.

    Args:
      path (str): path.

    Raises:
      ValueError: if the path is missing.
    """
    # TODO: add option to not look for partition and volume in path
    # TODO: determine file system path segment separator.

    super(PathFiltersGenerator, self).__init__()
    self._partition = None
    self._path_segments = path.split('/')

    if self._path_segments and not self._path_segments[0]:
      self._path_segments.pop(0)

    if self._path_segments and self._PARTITION_REGEX.match(
        self._path_segments[0]):
      self._partition = self._path_segments.pop(0)

    if not self._path_segments:
      raise ValueError('Missing path')

  @property
  def partition(self):
    """Retrieves the partition.

    Returns:
      str: partition defined by the path filter or None if not available.
    """
    return self._partition

  def GetFindSpecs(self):
    """Retrieves find specifications.

    Yields:
      dfvfs.FindSpec: file system (dfVFS) find specification.
    """
    yield dfvfs_file_system_searcher.FindSpec(location=self._path_segments)
