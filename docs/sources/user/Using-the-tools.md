# Using the tools

dfImageTools provides the following command line tools:

* extract_data_streams, to extract data streams from a storage media image;
* list_file_entries, to list metadata of file entries in a storage media image;
* map_extents, to map extents in a storage media image;
* recursive_hasher, to calculate a message digest hash for every file in a storage media image;
* source_analyzer, to analyze volumes and file systems in a storage media image.

When dfImageTools is installed with pip the tools are available as commands,
for example `source_analyzer`. From a checkout of the dfImageTools source code
run the corresponding script, for example:

```bash
PYTHONPATH=. python dfimagetools/scripts/source_analyzer.py image.raw
```

Where image.raw is the source, such as a storage media image, a device or a
directory.

Use `--help` to list all the options supported by a tool.

## extract_data_streams

**extract_data_streams** extracts data streams from a storage media image to
a target directory. At least one filter is required, for example an artifact
definition, a file name extension, a file name or a path.

```bash
extract_data_streams --name_filter passwords.txt -t export image.raw
```

By default a SHA-256 digest hash is calculated for each data stream,
duplicates are skipped and the hashes are written to `hashes.json` in the
target directory.

## list_file_entries

**list_file_entries** lists metadata of file entries in a storage media image.
The default output format is [bodyfile](../Bodyfile-format.md).

```bash
list_file_entries image.raw
```

## map_extents

**map_extents** maps extents in a storage media image to the corresponding
file entries.

```bash
map_extents image.raw
```

## recursive_hasher

**recursive_hasher** calculates a SHA-256 digest hash for every file in a
directory or storage media image.

```bash
recursive_hasher image.raw
```

## source_analyzer

**source_analyzer** analyzes the volumes and file systems in a storage media
image and can help pinpoint which part of the storage media image, for example
the storage media image format, a volume system or a file system, causes an
error.

```bash
source_analyzer image.raw
```

For example:

```
$ source_analyzer /home/user/image.qcow2
Source type             : storage media image

OS: location: /home/user/image.qcow2
  QCOW:
    EXT: location: /

Completed.
```

Use `--no-auto-recurse` to analyze the source one scan step at a time.

```bash
source_analyzer --no-auto-recurse image.raw
```
