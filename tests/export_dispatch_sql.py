"""Expose exact store SQL constants to the ephemeral PostgreSQL contract test."""
import ast
import json
from pathlib import Path
source=Path(__file__).resolve().parents[1]/'sahayak/dispatch/store.py'
tree=ast.parse(source.read_text())
result={}
for node in ast.walk(tree):
    if isinstance(node,ast.FunctionDef):
        result[node.name]=[n.args[0].value for n in ast.walk(node)
            if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='text'
            and n.args and isinstance(n.args[0],ast.Constant)]
print(json.dumps(result))
