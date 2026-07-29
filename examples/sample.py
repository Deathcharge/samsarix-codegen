"""Small input used by the README and package smoke test."""


def greet(name: str) -> str:
    """Return a friendly greeting."""

    cleaned_name = name.strip()
    if not cleaned_name:
        raise ValueError("name cannot be blank")
    return f"Hello, {cleaned_name}!"
