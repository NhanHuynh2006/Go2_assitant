import ast, sys, re
bad_api = re.compile(r"\.removeprefix\(|\.removesuffix\(|functools\.cache\b|from functools import cache\b|strict=True|\.bit_count\(|itertools\.pairwise|math\.lcm|\bmatch .*:\s*$|np\.trapezoid|np\.long\b|np\.bool\b|np\.int\b|np\.float\b|np\.in1d|copy=None|asarray\(.*copy=")
for f in sys.argv[1:]:
    src = open(f, encoding="utf-8").read()
    msgs = []
    try:
        tree = ast.parse(src, feature_version=(3, 8))
    except SyntaxError as e:
        msgs.append(f"SYNTAX(3.8): {e}")
        tree = ast.parse(src)
    fut = "from __future__ import annotations" in src
    for n in ast.walk(tree):
        anns = []
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            anns = [a.annotation for a in n.args.args + n.args.kwonlyargs if a.annotation] + ([n.returns] if n.returns else [])
        elif isinstance(n, ast.AnnAssign) and not isinstance(getattr(n, 'parent', None), ast.ClassDef):
            anns = [n.annotation]
        for a in anns:
            s = ast.unparse(a)
            if not fut and (re.search(r"\b(list|dict|tuple|set|type)\[", s) or "|" in s):
                msgs.append(f"line {a.lineno}: runtime annotation {s!r} fails on 3.8")
        if isinstance(n, ast.Call) and getattr(n.func, 'attr', '') in ('removeprefix', 'removesuffix'):
            msgs.append(f"line {n.lineno}: str.{n.func.attr} needs 3.9")
        if isinstance(n, ast.BinOp) and isinstance(n.op, ast.BitOr) and isinstance(n.left, ast.Dict):
            msgs.append(f"line {n.lineno}: dict | dict needs 3.9")
    for i, l in enumerate(src.splitlines(), 1):
        if bad_api.search(l) and not l.strip().startswith("#"):
            msgs.append(f"line {i}: check API: {l.strip()[:100]}")
    print(f, "OK" if not msgs else "")
    for m in msgs: print("   ", m)
