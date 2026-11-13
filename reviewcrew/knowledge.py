"""Small, curated Python review corpus for grounded agent responses."""

from langchain_core.documents import Document


GUIDANCE = [
    ("Input validation", "Validate inputs at public function boundaries. Check type, range, empty values and malformed data. Raise a clear ValueError or TypeError rather than silently coercing unexpected input."),
    ("Exception handling", "Catch only exceptions a function can meaningfully handle. Avoid broad except Exception blocks that hide programming errors. Preserve the original exception with chaining when translating errors."),
    ("Mutable defaults", "Never use a mutable list or dictionary as a Python function default. Use None and create a new collection inside the function so calls do not share state."),
    ("Resource management", "Use context managers such as with open(...) for files and locks. They close resources on success and on exceptions."),
    ("Side effects", "Prefer pure functions for transformations. Keep network, filesystem and global-state effects explicit. Avoid mutating caller-owned collections unless the contract says to do so."),
    ("Numeric edge cases", "Consider empty inputs, zero denominators, negative values, rounding, and overflow. Check boundaries and preserve the intended numeric type."),
    ("Naming and readability", "Use snake_case for functions and variables, descriptive names, focused functions, and early returns for guard conditions. Avoid shadowing built-ins such as list, id, or sum."),
    ("Testing", "Cover a normal case, a boundary case, and invalid input. Tests should assert outcomes rather than implementation details and should be deterministic."),
    ("Security", "Do not evaluate untrusted strings with eval or exec. Avoid shell=True with user-controlled input. Treat paths, deserialized data and external responses as untrusted."),
    ("Complexity", "Check nested loops and repeated work inside loops. Use a suitable set or dictionary for repeated membership and lookup operations when it improves clarity and complexity."),
]


def documents() -> list[Document]:
    return [Document(page_content=f"{title}: {body}", metadata={"title": title, "source": "ReviewCrew Python review guide"}) for title, body in GUIDANCE]
