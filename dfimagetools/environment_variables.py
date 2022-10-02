# -*- coding: utf-8 -*-
"""Windows environment variables collector."""

from dfimagetools import resources


class WindowsEnvironmentVariablesCollector(object):
  """Windows environment variables collector."""

  _ENVIRONMENT_KEY_PATH = (
      'HKEY_LOCAL_MACHINE\\System\\CurrentControlSet\\Control\\'
      'Session Manager\\Environment')

  _PROFILELIST_KEY_PATH = (
      'HKEY_LOCAL_MACHINE\\Software\\Microsoft\\Windows NT\\CurrentVersion\\'
      'ProfileList')

  _WINDOWS_CURRENTVERSION_KEY_PATH = (
      'HKEY_LOCAL_MACHINE\\Software\\Microsoft\\Windows\\CurrentVersion')

  _WINDOWS_NT_CURRENTVERSION_KEY_PATH = (
      'HKEY_LOCAL_MACHINE\\Software\\Microsoft\\Windows NT\\CurrentVersion')

  _PROFILELIST_KEY_VALUE_MAPPINGS = {
      'AllUsersProfile': '%AllUsersProfile%',
      'ProgramData': '%ProgramData%',
      'Public': '%Public%'}

  _WINDOWS_KEY_VALUE_MAPPINGS = {
      'CommonFilesDir': '%CommonProgramFiles%',
      'CommonFilesDir (x86)': '%CommonProgramFiles(x86)%',
      'CommonW6432Dir': '%CommonProgramW6432%',
      'ProgramFilesDir': '%ProgramFiles%',
      'ProgramFilesDir (x86)': '%ProgramFiles(x86)%',
      'ProgramW6432Dir': '%ProgramW6432%'}

  _WINDOWS_NT_KEY_VALUE_MAPPINGS = {
      'SystemRoot': '%SystemRoot%'}

  def _CollectEnvironmentVariablesFromEnvironmentKey(self, registry_key):
    """Collects environment variables.

    Args:
      registry_key (dfwinreg.WinRegistryKey): environment Windows Registry
          key.

    Yields:
      EnvironmentVariable: an environment variable.
    """
    for registry_value in registry_key.GetValues():
      value_string = registry_value.GetDataAsObject()
      yield resources.EnvironmentVariable(
          case_sensitive=False, name=f'%{registry_value.name:s}%',
          value=value_string)

  def _CollectEnvironmentVariablesWithMappings(self, registry_key, mappings):
    """Collects environment variables.

    Args:
      registry_key (dfwinreg.WinRegistryKey): Windows Registry key.

    Yields:
      EnvironmentVariable: an environment variable.
    """
    for value_name, environment_variable_name in mappings.items():
      registry_value = registry_key.GetValueByName(value_name)
      if registry_value:
        value_string = registry_value.GetDataAsObject()
        yield resources.EnvironmentVariable(
            case_sensitive=False, name=environment_variable_name,
            value=value_string)

  def Collect(self, registry):
    """Collects environment variables.

    Args:
      registry (dfwinreg.WinRegistry): Windows Registry.

    Yields:
      EnvironmentVariable: an environment variable.
    """
    registry_key = registry.GetKeyByPath(self._ENVIRONMENT_KEY_PATH)
    if registry_key:
      yield from self._CollectEnvironmentVariablesFromEnvironmentKey(
          registry_key)

    registry_key = registry.GetKeyByPath(self._PROFILELIST_KEY_PATH)
    if registry_key:
      yield from self._CollectEnvironmentVariablesWithMappings(
          registry_key, self._PROFILELIST_KEY_VALUE_MAPPINGS)

    registry_key = registry.GetKeyByPath(self._WINDOWS_CURRENTVERSION_KEY_PATH)
    if registry_key:
      yield from self._CollectEnvironmentVariablesWithMappings(
          registry_key, self._WINDOWS_KEY_VALUE_MAPPINGS)

    registry_key = registry.GetKeyByPath(
        self._WINDOWS_NT_CURRENTVERSION_KEY_PATH)
    if registry_key:
      yield from self._CollectEnvironmentVariablesWithMappings(
          registry_key, self._WINDOWS_NT_KEY_VALUE_MAPPINGS)
