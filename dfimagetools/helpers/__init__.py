"""Helper functions for CLI tools."""

from dfimagetools import decorators
from dfimagetools.helpers import backend


# This function is deprecated use the one in backend.py instead.
@decorators.deprecated
def SetDFVFSBackEnd(back_end):
    """Sets the dfVFS back-end.

    Args:
      back_end (str): dfVFS back-end.
    """
    backend.SetDFVFSBackEnd(back_end)
