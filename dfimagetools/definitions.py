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

NON_PRINTABLE_CHARACTER_TRANSLATION_TABLE = str.maketrans(
    NON_PRINTABLE_CHARACTERS)
