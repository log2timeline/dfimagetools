# -*- coding: utf-8 -*-
"""Helpers to collect information from the Windows Registry."""

from dfvfs.file_io import file_io as dfvfs_file_io
from dfvfs.helpers import windows_path_resolver
from dfvfs.lib import definitions as dfvfs_definitions
from dfvfs.resolver import resolver as dfvfs_resolver

from dfwinreg import creg as dfwinreg_creg
from dfwinreg import interface as dfwinreg_interface
from dfwinreg import regf as dfwinreg_regf
from dfwinreg import registry as dfwinreg_registry

from dfimagetools import environment_variables


class WindowsRegistryFile(dfwinreg_interface.WinRegistryFile):
  """Windows Registry file.

  This class manages a Windows Registry file-like object.
  """

  def __init__(self, ascii_codepage='cp1252', key_path_prefix=''):
    """Initializes a Windows Registry file.

    Args:
      ascii_codepage (Optional[str]): ASCII string codepage.
      key_path_prefix (Optional[str]): Windows Registry key path prefix.
    """
    super(WindowsRegistryFile, self).__init__()
    self._file_object = None
    self._registry_file = None

  def Close(self):
    """Closes the Windows Registry file."""
    self._registry_file.Close()
    self._registry_file = None

    if not isinstance(self._file_object, dfvfs_file_io.FileIO):
      self._file_object.close()
    self._file_object = None

  def GetKeyByPath(self, key_path):
    """Retrieves the key for a specific path.

    Args:
      key_path (str): Windows Registry key path.

    Returns:
      WinRegistryKey: Windows Registry key or None if not available.
    """
    return self._registry_file.GetKeyByPath(key_path)

  def GetRootKey(self):
    """Retrieves the root key.

    Returns:
      WinRegistryKey: Windows Registry root key or None if not available.
    """
    return self._registry_file.GetRootKey()

  def Open(self, file_object):
    """Opens the Windows Registry file using a file-like object.

    Args:
      file_object (file): file-like object.

    Raises:
      IOError: if the Windows Registry file cannot be opened.
      OSError: if the Windows Registry file cannot be opened.
    """
    try:
      registry_file = dfwinreg_regf.REGFWinRegistryFile(
          ascii_codepage=self._ascii_codepage,
          key_path_prefix=self._key_path_prefix)

      registry_file.Open(file_object)

    except IOError:
      registry_file = None

    if not registry_file:
      try:
        registry_file = dfwinreg_creg.CREGWinRegistryFile(
            ascii_codepage=self._ascii_codepage,
            key_path_prefix=self._key_path_prefix)

      except IOError:
        registry_file = None

    if not registry_file:
      raise IOError('Unable to open Windows Registry file.')

    self._file_object = file_object
    self._registry_file = registry_file

  def SetKeyPathPrefix(self, key_path_prefix):
    """Sets the Window Registry key path prefix.

    Args:
      key_path_prefix (str): Windows Registry key path prefix.
    """
    super(WindowsRegistryFile, self).SetKeyPathPrefix(key_path_prefix)
    if self._registry_file:
      self._registry_file.SetKeyPathPrefix(key_path_prefix)


class StorageMediaImageWindowsRegistryFileReader(
    dfwinreg_interface.WinRegistryFileReader):
  """Storage media image Windows Registry file reader."""

  def __init__(self, file_system, path_resolver):
    """Initializes a storage media Windows Registry file reader.

    Args:
      file_system (dfvfs.FileSystem): file system that contains the Windows
          directory.
      path_resolver (dfvfs.WindowsPathResolver): Windows path resolver.
    """
    super(StorageMediaImageWindowsRegistryFileReader, self).__init__()
    self._file_system = file_system
    self._path_resolver = path_resolver

  def Open(self, path, ascii_codepage='cp1252'):
    """Opens the Windows Registry file specified by the path.

    Args:
      path (str): path of the Windows Registry file. The path is a Windows path
          relative to the root of the file system that contains the specific
          Windows Registry file. E.g. C:\\Windows\\System32\\config\\SYSTEM
      ascii_codepage (Optional[str]): ASCII string codepage.

    Returns:
      WinRegistryFile: Windows Registry file or None if the file cannot
          be opened.
    """
    path_spec = self._path_resolver.ResolvePath(path)
    if path_spec is None:
      return None

    file_object = self._file_system.GetFileObjectByPathSpec(path_spec)
    if file_object is None:
      return None

    registry_file = WindowsRegistryFile(ascii_codepage=ascii_codepage)

    try:
      registry_file.Open(file_object)
      # Note that WindowsRegistryFile takes over management of file_object.
    except IOError:
      file_object.close()
      return None

    return registry_file


class WindowsRegistryCollector(object):
  """Windows Registry collector."""

  def __init__(self, path_spec, windows_directory):
    """Initializes a Windows Registry collector.

    Args:
      path_spec (PathSpec): path specification of the file system that contains
          the Windows Registry files.
      windows_directory (str): path of the Windows directory.
    """
    file_system = dfvfs_resolver.Resolver.OpenFileSystem(path_spec)

    if path_spec.type_indicator == dfvfs_definitions.TYPE_INDICATOR_OS:
      mount_point = path_spec
    else:
      mount_point = path_spec.parent

    path_resolver = windows_path_resolver.WindowsPathResolver(
        file_system, mount_point)

    path_resolver.SetEnvironmentVariable('SystemRoot', windows_directory)
    path_resolver.SetEnvironmentVariable('WinDir', windows_directory)

    # TODO: handle user Windows Registry files on different volumes.
    registry_file_reader = StorageMediaImageWindowsRegistryFileReader(
        file_system, path_resolver)

    super(WindowsRegistryCollector, self).__init__()
    self._registry = dfwinreg_registry.WinRegistry(
        registry_file_reader=registry_file_reader)

  def CollectSystemEnvironmentVariables(self):
    """Collects the system environment variables.

    Returns:
      list[EnvironmentVariable]: environment variables.
    """
    collector = environment_variables.WindowsEnvironmentVariablesCollector()
    return list(collector.Collect(self._registry))
