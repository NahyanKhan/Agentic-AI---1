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
    ("Mutation during iteration", "Changing a list while iterating over it can skip elements or produce surprising results. Iterate over a copy, build a new list, or use a comprehension."),
    ("Sorting assumptions", "Sorting may change input order in place when list.sort is used. Use sorted for a new list, and provide an explicit key when records need domain-specific ordering."),
    ("Off-by-one errors", "For index-based loops, verify the first and last valid index and whether the upper range bound is exclusive. Prefer direct iteration when an index is not required."),
    ("Boundary testing", "For a function accepting a collection, check empty and one-item inputs in addition to a typical multi-item input. For numeric thresholds, test just below, at, and just above the boundary."),
    ("Deterministic tests", "A useful test calls the function with a concrete input and checks an expected result. A check that only confirms a function exists does not verify its behavior."),
    ("Debugging an empty sequence", "Example bug: `return sum(values) / len(values)` raises ZeroDivisionError for an empty sequence. Decide whether empty input should return None, raise a clear ValueError, or have another documented result, then test that exact behavior."),
    ("Mutation debugging", "Example bug: removing items from a list while looping over that same list can skip the next item because indexes shift. Build a new filtered list or loop over a copy, and test adjacent matching items."),
    ("Boundary debugging", "Example bug: `range(len(items) - 1)` omits the last element and produces no iterations for a one-item list. Test lists of length zero, one, and two when changing index bounds."),
]

SOURCES = {
    "Mutable defaults": "https://docs.python.org/3/tutorial/controlflow.html#default-argument-values",
    "Exception handling": "https://docs.python.org/3/tutorial/errors.html",
    "Resource management": "https://docs.python.org/3/tutorial/inputoutput.html#reading-and-writing-files",
    "Naming and readability": "https://peps.python.org/pep-0008/",
    "Testing": "https://docs.python.org/3/library/unittest.html",
    "Deterministic tests": "https://docs.python.org/3/library/unittest.html",
    "Security": "https://docs.python.org/3/library/functions.html#eval",
    "Debugging an empty sequence": "https://docs.python.org/3/library/exceptions.html#ZeroDivisionError",
}


def documents() -> list[Document]:
    return [
        Document(
            page_content=f"{title}: {body}",
            metadata={"title": title, "source": SOURCES.get(title, "ReviewCrew curated debugging and Python review examples")},
        )
        for title, body in GUIDANCE
    ]
