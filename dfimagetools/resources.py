# -*- coding: utf-8 -*-
"""Various resource classes."""


class EnvironmentVariable(object):
  """Environment variable.

  Attributes:
    case_sensitive (bool): True if environment variable name is case sensitive.
    name (str): environment variable name such as "SystemRoot" as in
        "%SystemRoot%" or "HOME" as in "$HOME".
    value (str): environment variable value such as "C:\\Windows" or
        "/home/user".
  """

  def __init__(self, case_sensitive=True, name=None, value=None):
    """Initializes an environment variable.

    Args:
      case_sensitive (Optional[bool]): True if environment variable name
          is case sensitive.
      name (Optional[str]): environment variable name.
      value (Optional[str]): environment variable value.
    """
    super(EnvironmentVariable, self).__init__()
    self.case_sensitive = case_sensitive
    self.name = name
    self.value = value


class UserAccount(object):
  """User account.

  Attributes:
    full_name (str): name describing the user.
    group_identifier (str): identifier of the primary group the user is part of.
    identifier (str): user identifier.
    user_directory (str): path of the user (or home or profile) directory.
    user_directory_path_separator (str): path segment separator of the user
        directory.
    username (str): name uniquely identifying the user.
  """

  def __init__(
      self, full_name=None, group_identifier=None, identifier=None,
      user_directory=None, user_directory_path_separator='/', username=None):
    """Initializes a user account.

    Args:
      full_name (Optional[str]): name describing the user.
      group_identifier (Optional[str]): identifier of the primary group
          the user is part of.
      identifier (Optional[str]): user identifier.
      user_directory (Optional[str]): path of the user (or home or profile)
          directory.
      user_directory_path_separator (Optional[str]): path segment separator of
          the user directory.
      username (Optional[str]): name uniquely identifying the user.
    """
    super(UserAccount, self).__init__()
    self.full_name = full_name
    self.group_identifier = group_identifier
    self.identifier = identifier
    self.user_directory = user_directory
    self.user_directory_path_separator = user_directory_path_separator
    self.username = username
