# -*- coding: utf-8 -*-
"""Helper for resolving paths."""

import logging


class PathResolver(object):
  """Path resolver."""

  _GLOBSTAR_RECURSION_LIMIT = 10

  _PATH_EXPANSIONS_PER_USERS_VARIABLE = {
      '%%users.appdata%%': [
          ['%%users.userprofile%%', 'AppData', 'Roaming'],
          ['%%users.userprofile%%', 'Application Data']],
      '%%users.localappdata%%': [
          ['%%users.userprofile%%', 'AppData', 'Local'],
          ['%%users.userprofile%%', 'Local Settings', 'Application Data']],
      '%%users.localappdata_low%%': [
          ['%%users.userprofile%%', 'AppData', 'LocalLow']],
      '%%users.temp%%': [
          ['%%users.localappdata%%', 'Temp']]}

  _USER_DIRECTORY_VARIABLES = (
      '%%users.homedir%%', '%%users.userprofile%%')

  _WINDOWS_DRIVE_INDICATORS = (
      '%%environ_systemdrive%%', '%systemdrive%')

  def _CreateEnvironmentVariablesLookupTable(self, environment_variables):
    """Creates an environment variables lookup table.

    Args:
      environment_variables (list[EnvironmentVariable]): environment variables.

    Returns:
      dict[str, str]: environment variables lookup table.
    """
    lookup_table = {}
    for environment_variable in environment_variables or []:
      attribute_value = environment_variable.value
      if not isinstance(attribute_value, str):
        continue

      # Make the attribute name is in upper case and without the leading and
      # trailing %-characters.
      attribute_name = environment_variable.name.upper()
      if (len(attribute_name) >= 2 and attribute_name[0] == '%' and
          attribute_name[-1] == '%'):
        attribute_name = attribute_name[1:-1]

      lookup_table[attribute_name] = attribute_value

    if 'ALLUSERSAPPDATA' not in lookup_table:
      program_data = lookup_table.get('PROGRAMDATA', None)
      if program_data:
        lookup_table['ALLUSERSAPPDATA'] = program_data

    return lookup_table

  def _ExpandEnvironmentVariablesInPathSegments(
      self, path_segments, environment_variables):
    """Expands environment variables in path segments.

    Args:
      path_segments (list[str]): path segments with environment variables.
      environment_variables (list[EnvironmentVariable]): environment variables.

    Returns:
      list[str]: path segments with environment variables expanded.
    """
    if environment_variables is None:
      environment_variables = []

    lookup_table = self._CreateEnvironmentVariablesLookupTable(
        environment_variables)

    # Make a copy of path_segments since this loop can change it.
    for index, path_segment in enumerate(list(path_segments)):
      if (len(path_segment) <= 2 or not path_segment[0] == '%' or
          not path_segment[-1] == '%'):
        continue

      path_segment_upper_case = path_segment.upper()
      if path_segment_upper_case.startswith('%%ENVIRON_'):
        lookup_key = path_segment_upper_case[10:-2]
      else:
        lookup_key = path_segment_upper_case[1:-1]
      path_segment = lookup_table.get(lookup_key, path_segment)
      path_segment = path_segment.split('\\')

      expanded_path_segments = list(path_segments[:index])
      expanded_path_segments.extend(path_segment)
      expanded_path_segments.extend(path_segments[index + 1:])

      path_segments = expanded_path_segments

    if self._IsWindowsDrivePathSegment(path_segments[0]):
      path_segments[0] = ''

    return path_segments

  def _ExpandUserDirectoryVariableInPathSegments(
      self, path_segments, path_separator, user_accounts):
    """Expands a user directory variable in path segments.

    This method expands an artifact definition user directory variable such as
    %%users.homedir%% or %%users.userprofile%%.

    Args:
      path_segments (list[str]): path segments.
      path_separator (str): path segment separator.
      user_accounts (list[UserAccount]): user accounts.

    Returns:
      list[str]: paths returned for user accounts without a drive indicator.
    """
    if not path_segments:
      return []

    user_paths = []

    first_path_segment = path_segments[0].lower()
    if first_path_segment not in self._USER_DIRECTORY_VARIABLES:
      if self._IsWindowsDrivePathSegment(path_segments[0]):
        path_segments[0] = ''

      user_path = path_separator.join(path_segments)
      user_paths.append(user_path)

    elif not user_accounts:
      # Default to "Documents and Settings", "home" and "Users"
      user_path = path_separator.join(
          ['', 'Documents and Settings', '*'] + path_segments[1:])
      user_paths.append(user_path)

      user_path = path_separator.join(['', 'home', '*'] + path_segments[1:])
      user_paths.append(user_path)

      user_path = path_separator.join(['', 'Users', '*'] + path_segments[1:])
      user_paths.append(user_path)

    else:
      for user_account in user_accounts:
        if not user_account.user_directory:
          continue

        user_path_segments = user_account.user_directory.split(
            user_account.user_directory_path_separator)

        if self._IsWindowsDrivePathSegment(user_path_segments[0]):
          user_path_segments[0] = ''

        # Prevent concatenating two consecutive path segment separators.
        if not user_path_segments[-1]:
          user_path_segments.pop()

        user_path_segments.extend(path_segments[1:])

        user_path = path_separator.join(user_path_segments)
        user_paths.append(user_path)

    return user_paths

  def _ExpandUsersVariableInPathSegments(
      self, path_segments, path_separator, user_accounts):
    """Expands a users variable in path segments.

    This method expands an artifact definition user variable such as
    %%users.appdata%% or %%users.temp%%.

    Args:
      path_segments (list[str]): path segments.
      path_separator (str): path segment separator.
      user_accounts (list[UserAccount]): user accounts.

    Returns:
      list[str]: paths for which the users variables have been expanded.
    """
    if not path_segments:
      return []

    path_segments_lower = [
        path_segment.lower() for path_segment in path_segments]

    if path_segments_lower[0] in self._USER_DIRECTORY_VARIABLES:
      return self._ExpandUserDirectoryVariableInPathSegments(
          path_segments, path_separator, user_accounts)

    path_expansions = self._PATH_EXPANSIONS_PER_USERS_VARIABLE.get(
        path_segments[0], None)

    if path_expansions:
      expanded_paths = []

      for path_expansion in path_expansions:
        expanded_path_segments = list(path_expansion)
        expanded_path_segments.extend(path_segments[1:])

        paths = self._ExpandUsersVariableInPathSegments(
            expanded_path_segments, path_separator, user_accounts)
        expanded_paths.extend(paths)

      return expanded_paths

    if self._IsWindowsDrivePathSegment(path_segments[0]):
      path_segments[0] = ''

    # TODO: add support for %%users.username%%
    path = path_separator.join(path_segments)
    return [path]

  def _IsWindowsDrivePathSegment(self, path_segment):
    """Determines if the path segment contains a Windows Drive indicator.

    A drive indicator can be a drive letter, %SystemDrive% or the artifact
    definition environment variable %%environ_systemdrive%%.

    Args:
      path_segment (str): path segment.

    Returns:
      bool: True if the path segment contains a Windows Drive indicator.
    """
    if (len(path_segment) == 2 and path_segment[1] == ':' and
        path_segment[0].isalpha()):
      return True

    path_segment_lower = path_segment.lower()
    return path_segment_lower in self._WINDOWS_DRIVE_INDICATORS

  def ExpandEnvironmentVariables(
      self, path, path_separator, environment_variables):
    """Expands environment variables.

    Args:
      path (str): path with environment variables.
      path_separator (str): path segment separator.
      environment_variables (list[EnvironmentVariable]): environment variables.

    Returns:
      str: path with environment variables expanded.
    """
    path_segments = path.split(path_separator)
    path_segments = self._ExpandEnvironmentVariablesInPathSegments(
        path_segments, environment_variables)
    return path_separator.join(path_segments)

  def ExpandGlobStars(self, path, path_separator):
    """Expands globstars "**".

    A globstar "**" will recursively match all files and zero or more
    directories and subdirectories.

    By default the maximum recursion depth is 10 subdirectories, a numeric
    values after the globstar, such as "**5", can be used to define the maximum
    recursion depth.

    Args:
      path (str): path with globstars.
      path_separator (str): path segment separator.

    Returns:
      str: path with seperate globs for every globstar.
    """
    expanded_paths = []

    path_segments = path.split(path_separator)
    last_segment_index = len(path_segments) - 1
    for segment_index, path_segment in enumerate(path_segments):
      recursion_depth = None
      if path_segment.startswith('**'):
        if len(path_segment) == 2:
          recursion_depth = 10
        else:
          try:
            recursion_depth = int(path_segment[2:], 10)
          except (TypeError, ValueError):
            logging.warning((
                'Globstar with suffix "{0:s}" in path "{1:s}" not '
                'supported.').format(path_segment, path))

      elif '**' in path_segment:
        logging.warning((
            'Globstar with prefix "{0:s}" in path "{1:s}" not '
            'supported.').format(path_segment, path))

      if recursion_depth is not None:
        if (recursion_depth <= 1 or
            recursion_depth > self._GLOBSTAR_RECURSION_LIMIT):
          logging.warning((
              'Globstar "{0:s}" in path "{1:s}" exceed recursion maximum '
              'recursion depth, limiting to: {2:d}.').format(
                  path_segment, path, self._GLOBSTAR_RECURSION_LIMIT))
          recursion_depth = self._GLOBSTAR_RECURSION_LIMIT

        next_segment_index = segment_index + 1
        for expanded_path_segment in [
            ['*'] * depth for depth in range(1, recursion_depth + 1)]:
          expanded_path_segments = list(path_segments[:segment_index])
          expanded_path_segments.extend(expanded_path_segment)
          if next_segment_index <= last_segment_index:
            expanded_path_segments.extend(path_segments[next_segment_index:])

          expanded_path = path_separator.join(expanded_path_segments)
          expanded_paths.append(expanded_path)

    return expanded_paths or [path]

  def ExpandUsersVariable(self, path, path_separator, user_accounts):
    """Expands a users variable, such as %%users.appdata%%.

    Args:
      path (str): path with users variable.
      path_separator (str): path segment separator.
      user_accounts (list[UserAccount]): user accounts.

    Returns:
      list[str]: paths for which the users variables have been expanded.
    """
    path_segments = path.split(path_separator)
    return self._ExpandUsersVariableInPathSegments(
        path_segments, path_separator, user_accounts)
