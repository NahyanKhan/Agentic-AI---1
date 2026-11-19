"""Deterministic Python code checks; these complement, not replace, a human review."""

from __future__ import annotations

import ast
import re
from dataclasses import asdict, dataclass


@dataclass
class Finding:
    severity: str
    category: str
    message: str
    line: int | None = None
    suggestion: str = ""

    def as_dict(self):
        return asdict(self)


def analyze(code: str) -> tuple[list[Finding], ast.Module | None, str | None]:
    try:
        tree = ast.parse(code or "")
    except SyntaxError as exc:
        return [Finding("error", "Syntax", exc.msg, exc.lineno, "Correct the syntax before running or testing this code.")], None, exc.msg

    # Add parent links for context-aware AST analysis
    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            child._parent = parent

    found: list[Finding] = []
    for node in ast.walk(tree):
        line = getattr(node, "lineno", None)
        if isinstance(node, ast.FunctionDef):
            positional = node.args.args
            defaults = node.args.defaults
            default_start = len(positional) - len(defaults)
            for _index, default in enumerate(defaults, start=default_start):
                if isinstance(default, (ast.List, ast.Dict, ast.Set)) or (
                    isinstance(default, ast.Call)
                    and isinstance(default.func, ast.Name)
                    and default.func.id in {"list", "dict", "set"}
                ):
                    found.append(
                        Finding(
                            "high",
                            "Correctness",
                            f"Mutable default in `{node.name}` is shared across calls.",
                            default.lineno,
                            "Use None as the default and create a new value inside the function.",
                        )
                    )
            if not re.fullmatch(r"[a-z_][a-z0-9_]*", node.name):
                found.append(Finding("low", "Style", f"Function `{node.name}` is not snake_case.", line, "Use a descriptive snake_case name."))
            if len(node.body) > 45:
                found.append(Finding("medium", "Maintainability", f"`{node.name}` has a long body ({len(node.body)} top-level statements).", line, "Split distinct responsibilities into smaller helpers."))

        elif isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Param)):
            if node.id in {"list", "dict", "set", "id", "sum", "type", "input", "str", "int", "max", "min", "open"}:
                found.append(Finding("medium", "Correctness", f"Name `{node.id}` shadows a Python built-in.", line, "Rename it so the built-in remains available."))

        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id in {"eval", "exec"}:
                found.append(Finding("high", "Security", f"`{node.func.id}()` executes dynamically constructed code.", line, "Avoid evaluating untrusted text; use a constrained parser for the expected format."))
            elif isinstance(node.func, ast.Name) and node.func.id == "open":
                # Check if called outside a 'with' statement
                curr = getattr(node, "_parent", None)
                in_with = False
                while curr:
                    if isinstance(curr, ast.With):
                        in_with = True
                        break
                    curr = getattr(curr, "_parent", None)
                if not in_with:
                    found.append(Finding("medium", "Reliability", "File opened without a `with` statement context manager.", line, "Use `with open(...)` to ensure the file descriptor is cleanly closed."))

        elif isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
            if isinstance(node.right, ast.Constant) and node.right.value == 0:
                found.append(Finding("high", "Correctness", "Division by zero will raise ZeroDivisionError at runtime.", line, "Ensure the divisor cannot be zero."))
            elif isinstance(node.right, ast.Call) and isinstance(node.right.func, ast.Name) and node.right.func.id == "len":
                found.append(Finding("high", "Correctness", "Division by `len(...)` can raise ZeroDivisionError if the sequence is empty.", line, "Guard with a non-empty sequence check or provide a default for empty input."))

        elif isinstance(node, ast.ExceptHandler):
            if node.type is None:
                found.append(Finding("medium", "Reliability", "Bare `except:` catches all exceptions including system interrupts.", line, "Catch specific exception types instead."))
            elif isinstance(node.type, ast.Name) and node.type.id == "Exception":
                found.append(Finding("medium", "Reliability", "Broad `except Exception:` can mask programming bugs and logic errors.", line, "Catch the specific exception types the code is prepared to recover from."))

        elif isinstance(node, ast.For):
            if isinstance(node.iter, ast.Call) and isinstance(node.iter.func, ast.Name) and node.iter.func.id == "range" and len(node.iter.args) == 1 and isinstance(node.iter.args[0], ast.Call):
                found.append(Finding("low", "Readability", "A computed range bound is evaluated before the loop starts.", line, "If the bound depends on a list being changed in the loop, clarify the intended behavior."))

        elif isinstance(node, ast.Compare):
            if any(isinstance(op, (ast.Eq, ast.NotEq)) and isinstance(comp, ast.Constant) and comp.value is None for op, comp in zip(node.ops, node.comparators, strict=False)):
                found.append(Finding("low", "Style", "Use `is None` or `is not None` when checking for None.", line, "Replace equality comparison with identity comparison."))

    # Deduplicate findings
    unique = {(f.severity, f.category, f.message, f.line): f for f in found}
    return list(unique.values()), tree, None


def score(findings: list[Finding]) -> dict[str, int]:
    deductions = {"high": 18, "medium": 9, "low": 3, "error": 35}
    correctness_cats = {"correctness", "security", "syntax", "reliability", "logic", "runtime", "edge case", "bug"}
    style_cats = {"style", "readability", "maintainability", "convention"}

    correctness_deduction = sum(
        deductions.get(f.severity.lower(), 9)
        for f in findings
        if f.category.lower() in correctness_cats
    )
    style_deduction = sum(
        deductions.get(f.severity.lower(), 3)
        for f in findings
        if f.category.lower() in style_cats
    )
    for f in findings:
        cat_lower = f.category.lower()
        if cat_lower not in correctness_cats and cat_lower not in style_cats:
            if f.severity.lower() in {"high", "error"}:
                correctness_deduction += deductions.get(f.severity.lower(), 18)
            else:
                style_deduction += deductions.get(f.severity.lower(), 3)

    correctness = max(0, 100 - correctness_deduction)
    style = max(0, 100 - style_deduction)
    return {"Correctness": correctness, "Style": style, "Overall": round((correctness * 0.7) + (style * 0.3))}


def function_names(tree: ast.Module | None) -> list[str]:
    if tree is None:
        return []
    return [n.name for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]


def generate_fallback_tests(tree: ast.Module | None) -> list[dict]:
    """Generate basic initial behavior checks from function signatures when offline."""
    tests = []
    if tree is None:
        return tests
    for node in tree.body:
        if isinstance(node, ast.FunctionDef):
            name = node.name
            args = node.args.args
            if not args:
                tests.append({
                    "name": f"test_{name}_no_args",
                    "assertion": f"assert {name}() is not None or True",
                    "purpose": f"Execute `{name}()` with no arguments to verify basic execution.",
                })
            else:
                arg_names = [a.arg for a in args]
                tests.append({
                    "name": f"test_{name}_signature",
                    "assertion": f"assert callable({name})",
                    "purpose": f"Verify `{name}` is defined and callable with parameters: {', '.join(arg_names)}.",
                })
    return tests
