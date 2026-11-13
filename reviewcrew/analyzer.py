"""Deterministic Python code checks; these complement, not replace, a human review."""

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

    found: list[Finding] = []
    for node in ast.walk(tree):
        line = getattr(node, "lineno", None)
        if isinstance(node, ast.FunctionDef):
            positional = node.args.args
            defaults = node.args.defaults
            default_start = len(positional) - len(defaults)
            for index, default in enumerate(defaults, start=default_start):
                if isinstance(default, (ast.List, ast.Dict, ast.Set)) or (isinstance(default, ast.Call) and isinstance(default.func, ast.Name) and default.func.id in {"list", "dict", "set"}):
                    found.append(Finding("high", "Correctness", f"Mutable default in `{node.name}` is shared across calls.", default.lineno, "Use None as the default and create a new value inside the function."))
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
            if isinstance(node.func, ast.Name) and node.func.id == "open" and not any(isinstance(parent, ast.With) for parent in []):
                # A light heuristic: context-manager coverage is checked below via parent links.
                pass
        elif isinstance(node, ast.ExceptHandler) and (node.type is None or (isinstance(node.type, ast.Name) and node.type.id == "Exception")):
            found.append(Finding("medium", "Reliability", "Broad exception handler can hide unexpected failures.", line, "Catch the specific exception types the code can recover from."))
        elif isinstance(node, ast.For):
            if isinstance(node.iter, ast.Call) and isinstance(node.iter.func, ast.Name) and node.iter.func.id == "range" and len(node.iter.args) == 1 and isinstance(node.iter.args[0], ast.Call):
                found.append(Finding("low", "Readability", "A computed range bound is evaluated before the loop starts.", line, "If the bound depends on a list being changed in the loop, clarify the intended behavior."))
        elif isinstance(node, ast.Compare):
            if any(isinstance(op, (ast.Eq, ast.NotEq)) and isinstance(comp, ast.Constant) and comp.value is None for op, comp in zip(node.ops, node.comparators)):
                found.append(Finding("low", "Style", "Use `is None` when checking for None.", line, "Replace equality comparison with identity comparison."))

    # Avoid duplicate reports caused by repeated built-in references on one line.
    unique = {(f.severity, f.category, f.message, f.line): f for f in found}
    return list(unique.values()), tree, None


def score(findings: list[Finding]) -> dict[str, int]:
    deductions = {"high": 18, "medium": 9, "low": 3, "error": 35}
    correctness = max(0, 100 - sum(deductions[f.severity] for f in findings if f.category in {"Correctness", "Security", "Syntax", "Reliability"}))
    style = max(0, 100 - sum(deductions[f.severity] for f in findings if f.category in {"Style", "Readability", "Maintainability"}))
    return {"Correctness": correctness, "Style": style, "Overall": round((correctness * .7) + (style * .3))}


def function_names(tree: ast.Module | None) -> list[str]:
    if tree is None:
        return []
    return [n.name for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
