import ast
import sys


def defs(p):
    t = ast.parse(open(p, encoding="utf-8").read())
    out = {}
    for n in t.body:
        if isinstance(n, (ast.FunctionDef, ast.ClassDef, ast.AsyncFunctionDef)):
            out[n.name] = ast.dump(n)
        elif isinstance(n, (ast.Assign, ast.AnnAssign)):
            tg = n.targets[0] if isinstance(n, ast.Assign) else n.target
            if isinstance(tg, ast.Name):
                out[tg.id] = ast.dump(n)
    return out


o, n = defs(sys.argv[1]), defs(sys.argv[2])
print("old", len(o), "new", len(n))
print(
    "unchanged",
    sum(1 for k in o if k in n and o[k] == n[k]),
    "changed",
    [k for k in o if k in n and o[k] != n[k]],
)
print("only new", [k for k in n if k not in o])
