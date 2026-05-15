"""The dfImageTools definitions."""

# Characters that are considered non-printable Unicode characters.
NON_PRINTABLE_CHARACTERS = {}

# Escape C0 control characters as \x##
NON_PRINTABLE_CHARACTERS.update({value: f"\\x{value:02x}" for value in range(0, 0x20)})

# Escape C1 control character as \x##
NON_PRINTABLE_CHARACTERS.update(
    {value: f"\\x{value:02x}" for value in range(0x7F, 0xA0)}
)

# Escape Unicode surrogate characters as \U########
NON_PRINTABLE_CHARACTERS.update(
    {value: f"\\U{value:08x}" for value in range(0xD800, 0xE000)}
)

# Escape undefined Unicode characters as \U########
NON_PRINTABLE_CHARACTERS.update(
    {
        value: f"\\U{value:08x}"
        for value in (
            0xFDD0,
            0xFDD1,
            0xFDD2,
            0xFDD3,
            0xFDD4,
            0xFDD5,
            0xFDD6,
            0xFDD7,
            0xFDD8,
            0xFDD9,
            0xFDDA,
            0xFDDB,
            0xFDDC,
            0xFDDD,
            0xFDDE,
            0xFDDF,
            0xFFFE,
            0xFFFF,
            0x1FFFE,
            0x1FFFF,
            0x2FFFE,
            0x2FFFF,
            0x3FFFE,
            0x3FFFF,
            0x4FFFE,
            0x4FFFF,
            0x5FFFE,
            0x5FFFF,
            0x6FFFE,
            0x6FFFF,
            0x7FFFE,
            0x7FFFF,
            0x8FFFE,
            0x8FFFF,
            0x9FFFE,
            0x9FFFF,
            0xAFFFE,
            0xAFFFF,
            0xBFFFE,
            0xBFFFF,
            0xCFFFE,
            0xCFFFF,
            0xDFFFE,
            0xDFFFF,
            0xEFFFE,
            0xEFFFF,
            0xFFFFE,
            0xFFFFF,
            0x10FFFE,
            0x10FFFF,
        )
    }
)

# Escape observed non-printable Unicode characters as \U########
NON_PRINTABLE_CHARACTERS.update(
    {
        value: f"\\U{value:08x}"
        for value in (
            0x2028,
            0x2029,
            0xE000,
            0xF8FF,
            0xF0000,
            0xFFFFD,
            0x100000,
            0x10FFFD,
        )
    }
)

NON_PRINTABLE_CHARACTER_TRANSLATION_TABLE = str.maketrans(NON_PRINTABLE_CHARACTERS)
