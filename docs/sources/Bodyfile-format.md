# Bodyfile format

The bodyfile (or body file) format is an output format, as far as known,
introduced by the SleuthKit. SleuthKit tools such as fls or ils, use a
bodyfile for intermediate storage. These bodyfiles are then provided as
input to the mactime tool.

The bodyfile format has been adopted by many other, non-SleuthKit tools, and
does not appear to have a strict definition. This document explains
the implementation used by the imagetools project.

The imagetools project uses a bodyfile format that has been derived from
the format used by SleuthKit 3.0 and later. Changes have been made to overcome
several shortcomings of the original format.

A bodyfile consists of one or more lines with 11 pipe-character ('|') delimited
values. The [SleuthKit documentation](https://wiki.sleuthkit.org/index.php?title=Body_file)
defines these values as:

```
MD5|name|inode|mode_as_string|UID|GID|size|atime|mtime|ctime|crtime
```

Value | Description
--- | ---
MD5 | MD5 of the file entry data.
name | Full path of the file entry.
inode | Unique identifier of the file entry within the file system.
mode_as_string | POSIX file mode represented as a string for example 'drwx------'. <br> The SleuthKit specific `-/` prefix is not used by the `list_file_entries.py` script.
UID | POSIX user identifier (UID) of the user owning the file entry. <br> Note that this value will be empty if the file system has no user identifier equivalent.
GID | POSIX group identifier (GID) of the group owning the file entry. <br> Note that this value will be empty if the file system has no group identifier equivalent.
size | Size of the data of the file entry. <br> Note that the `list_file_entries.py` script only reports the size of "regular" file entries.
atime | File entry last access time.
mtime | File entry last modification time.
ctime | File entry last change (or entry modification) time.
crtime | File entry creation time.

## MD5 value

The SleuthKit documentation does not define the MD5 values. From observations
the following convention is used:

* '0' if "hashing" is disabled;
* '00000000000000000000000000000000' if "hashing" is enabled but no MD5 was calculated;
* '[0-9a-f]{32}' if a MD5 was calculated.

## Name value

The name value typically contains a full path of the file entry, but it can also
contain a symobolic link target using the convention:

```
${PATH} -> ${SYMBOLIC_LINK_TARGET}
```

Bodyfile entries where the time values are extracted for an NTFS $FILE_NAME
attribute the '($FILE_NAME)' suffix is added to the name value.

```
${PATH} (\$FILE_NAME)
```

Note that at the moment the `list_file_entries.py` script does not combine
a symbolic link target and '($FILE_NAME)' suffix.

The `list_file_entries.py` script always uses forward slash ('/') as the path
segment separator, even for NTFS. The following characters are escaped with
a backslash ('\\'):

* U+0000 - U+0019 (C0 control codes, non-printable)
* U+002f (forward slash '/', used as path segment separator)
* U+003a (colon ':', used as data stream separator)
* U+005c (backslash '\\', used as escape character)
* U+007c (pipe '|', used as value delimiter)
* U+007f (delete, non-printable)
* U+0080 - U+009f (C1 control codes, non-printable)

Paths are prefixed with a partition or volume indicator if
the `list_file_entries.py` script is used to list multiple partitions and/or
volumes at once.

## Inode value

The inode value contains an unique identifier of the file entry within the file
system, which for some file systems is the inode number.

For NTFS the convention `${MFT_ENTRY}-${SEQUENCE_NUMBER}` is used instead of
the non-portable [metadata address](https://wiki.sleuthkit.org/index.php?title=Metadata_Address)
used by the SleuthKit tools.

## Time values

Time values are provided as a number of seconds since January 1, 1970 00:00:00
(epoch) without a time zone, where negative time values predate the epoch.
A fraction of second is provided if the original time value has a higher
[datetime value granularity](https://dfdatetime.readthedocs.io/en/latest/sources/Date-and-time-values.html#terminology).

## Also see

* [Forensics wiki: Bodyfile](https://forensicswiki.xyz/wiki/index.php?title=Bodyfile)
* [SleuthKit: Body file](https://wiki.sleuthkit.org/index.php?title=Body_file)
