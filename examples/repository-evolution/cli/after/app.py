"""Synthetic CLI after a bounded simulated review."""

def parse_count(value):
    try:
        return int(value)
    except ValueError:
        raise ValueError("count must be an integer") from None
