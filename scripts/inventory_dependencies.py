#!/usr/bin/env python3
"""Inventory runtime imports, lazy imports and resolved distributions read-only.

Not an unused-package remover: optional SDKs and transitive providers remain
until a separate feature-specific removal proves their full call graph.
"""
import argparse
import ast
import importlib.metadata
import json
from pathlib import Path
import sys


def inventory(root):
    backend = root / "backend"
    local = {p.stem for p in backend.glob("*.py")} | {p.name for p in backend.iterdir() if p.is_dir()}
    providers = importlib.metadata.packages_distributions()
    imports, dynamic = {}, []
    for path in sorted(backend.rglob("*.py")):
        if any(part in {"tests", "venv", ".venv", "__pycache__"} for part in path.relative_to(backend).parts):
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        parents = {}
        for parent in ast.walk(tree):
            for child in ast.iter_child_nodes(parent):
                parents[child] = parent
        for node in ast.walk(tree):
            modules = []
            if isinstance(node, ast.Import):
                modules = [alias.name.split(".")[0] for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and not node.level and node.module:
                modules = [node.module.split(".")[0]]
            for module in modules:
                if module in sys.stdlib_module_names or module in local:
                    continue
                ancestor, lazy, optional = node, False, False
                while ancestor in parents:
                    ancestor = parents[ancestor]
                    lazy |= isinstance(ancestor, (ast.FunctionDef, ast.AsyncFunctionDef))
                    optional |= isinstance(ancestor, ast.Try)
                item = imports.setdefault(module, {"distributions": providers.get(module, []), "locations": []})
                item["locations"].append({"path": str(path.relative_to(root)), "line": node.lineno,
                                           "lazy": lazy, "try_guarded": optional})
            if isinstance(node, ast.Call):
                called = ast.unparse(node.func)
                if called == "__import__" or called.endswith("import_module"):
                    dynamic.append({"path": str(path.relative_to(root)), "line": node.lineno,
                                    "call": ast.unparse(node)})
    distributions = sorted(({"name": dist.metadata["Name"], "version": dist.version}
                            for dist in importlib.metadata.distributions()), key=lambda row: row["name"].lower())
    return {"python": sys.version.split()[0], "runtime_imports": imports,
            "dynamic_imports": dynamic, "installed_distributions": distributions,
            "policy": "No dependency is removed merely because no direct import was found."}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = json.dumps(inventory(Path(__file__).resolve().parents[1]), indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(result)
    else:
        print(result, end="")
