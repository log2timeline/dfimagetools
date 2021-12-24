# Bodyfile format

The bodyfile (or body file) format is an output format, as far as known,
introduced by the SleuthKit. SleuthKit tools such as fls or ils, use a
bodyfile for intermediate storage. These bodyfile sare then provided as
input to the mactime tool.

The bodyfile format has been adopted by many other, non-SleuthKit tools, and
does not appear to have a strict definition. Hence this document explaining
the implementation used by the imagetools project.

The `list_file_entries.py` script uses a bodyfile format that has been derived
from the fomrat used by SleuthKit 3.0 and later. Changes have been made to
overcome several shortcomings of the original format.

The bodyfile consists of 11 pipe-character (|) delimited values. The
[SleuthKit documentation](https://wiki.sleuthkit.org/index.php?title=Body_file)
defines these values as:

```
MD5|name|inode|mode_as_string|UID|GID|size|atime|mtime|ctime|crtime
```

Value | Description
--- | ---
MD5 | The SleuthKit documentation does not define the MD5 values.<br>From observations the following convention is used:<br>'0' if "hashing" is disabled,<br>'00000000000000000000000000000000' if "hashing" is enabled but no MD5 was calculated,<br>otherwise it contains the MD5 that was calculated.
name | Full path of the file entry, where the path segment separator is always `/`, even for NTFS, and paths can be prefixed with a partition indicator.
inode | Unique identifier of the file entry within the file system, which for some file systems is the inode number.<br>For NTFS the convention `${MFT_ENTRY}-${SEQUENCE_NUMBER}` is used in contast to the non-portable [metadata address](https://wiki.sleuthkit.org/index.php?title=Metadata_Address) used by the SleuthKit tools.<br>Note the name value also can contain a symobolic link target using the convention `${PATH} -> ${SYMBOLIC_LINK_TARGET}`.<rb>The '($FILE_NAME)' suffix is not used by `list_file_entries.py`.
mode_as_string | POSIX file mode represented as a string for example 'drwx------'.<br>The SleuthKit specific `-/` prefix is not used by `list_file_entries.py`.
UID | POSIX user identifier (UID) of the user owning the file entry.<br>Note that this value will be empty if the file system has no user identifier equivalent.
GID | POSIX group identifier (GID) of the group owning the file entry.<br>Note that this value will be empty if the file system has no group identifier equivalent.
size | Size of the data of the file entry.<br>Note that `list_file_entries.py` only reports the size of "regular" file entries.
atime | File entry last access time.
mtime | File entry last modification time.
ctime | File entry last change (or entry modification) time.
crtime | File entry creation time.

Note that time values are provided in seconds since January 1, 1970 00:00:00
(epoch) without a time zone, where negative time values predate the epoch.
A fraction of second is provided if the original time value has a higher
[datetime value granularity](https://dfdatetime.readthedocs.io/en/latest/sources/Date-and-time-values.html#terminology).

## Also see

* [Forensics wiki: Bodyfile](https://forensicswiki.xyz/wiki/index.php?title=Bodyfile)
* [SleuthKit: Body file](https://wiki.sleuthkit.org/index.php?title=Body_file)
