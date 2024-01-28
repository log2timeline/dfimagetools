# -*- coding: utf-8 -*-
"""The dfImageTools definitions."""


# Characters that are considered non-printable Unicode characters.
NON_PRINTABLE_CHARACTERS = {}

# Escape C0 control characters as \x##
NON_PRINTABLE_CHARACTERS.update({
    value: f'\\x{value:02x}' for value in range(0, 0x20)})

# Escape C1 control character as \x##
NON_PRINTABLE_CHARACTERS.update({
    value: f'\\x{value:02x}' for value in range(0x7f, 0xa0)})

# Escape Unicode surrogate characters as \U########
NON_PRINTABLE_CHARACTERS.update({
    value: f'\\U{value:08x}' for value in range(0xd800, 0xe000)})

# Escape undefined Unicode characters as \U########
NON_PRINTABLE_CHARACTERS.update({value: f'\\U{value:08x}' for value in (
    0xfdd0, 0xfdd1, 0xfdd2, 0xfdd3, 0xfdd4, 0xfdd5, 0xfdd6, 0xfdd7, 0xfdd8,
    0xfdd9, 0xfdda, 0xfddb, 0xfddc, 0xfddd, 0xfdde, 0xfddf, 0xfffe, 0xffff,
    0x1fffe, 0x1ffff, 0x2fffe, 0x2ffff, 0x3fffe, 0x3ffff, 0x4fffe, 0x4ffff,
    0x5fffe, 0x5ffff, 0x6fffe, 0x6ffff, 0x7fffe, 0x7ffff, 0x8fffe, 0x8ffff,
    0x9fffe, 0x9ffff, 0xafffe, 0xaffff, 0xbfffe, 0xbffff, 0xcfffe, 0xcffff,
    0xdfffe, 0xdffff, 0xefffe, 0xeffff, 0xffffe, 0xfffff, 0x10fffe,
    0x10ffff)})

# Escape observed non-printable Unicode characters as \U########
NON_PRINTABLE_CHARACTERS.update({value: f'\\U{value:08x}' for value in (
    0x2028, 0x2029, 0xe000, 0xf8ff, 0xf0000, 0xffffd, 0x100000, 0x10fffd)})

NON_PRINTABLE_CHARACTER_TRANSLATION_TABLE = str.maketrans(
    NON_PRINTABLE_CHARACTERS)
