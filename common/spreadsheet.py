"""CSV cells that Excel shows as written.

Excel reads a cell that starts with = + - or @ as a formula: "-5 degrees"
shows as #NAME?, and text from a crafted PDF such as =HYPERLINK(...) would
run.  Such cells get a leading apostrophe, the usual way to mark a cell as
text.
"""

_FORMULA_START = ("=", "+", "-", "@", "\t", "\r")


def safe_cell(value):
    """*value* for a CSV opened in Excel (strings starting like a formula get a leading "'")."""
    if isinstance(value, str) and value.startswith(_FORMULA_START):
        return "'" + value
    return value


def safe_row(row) -> list:
    return [safe_cell(value) for value in row]
