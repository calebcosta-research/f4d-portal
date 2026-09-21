"""Safe parsing of structured answers read back from the database.

The app saves structured answers (deliverables, indicators, operations and so
on) with ``str(obj)``, so what comes back is Python repr text. Some readers used
Python's built-in evaluator on it, which runs any code that finds its way into
the database.

``parse_stored`` reads the same text but can only build data. It tries
``ast.literal_eval`` first, so anything that already parses that way gives
exactly the same result as before. Only if that fails does it fall back to a
strict reader that also accepts the date and time values ``st.date_input``
produces -- e.g. ``datetime.date(2026, 7, 15)`` -- which ``literal_eval``
rejects but the old evaluator accepted. Nothing else is allowed: no names, no
attribute access, no calls other than those constructors.
"""
import ast
import datetime

# The only constructors a stored value may contain, spelled as repr() writes
# them. Positional integer arguments only.
_CONSTRUCTORS = {
    "datetime.date": datetime.date,
    "datetime.datetime": datetime.datetime,
    "datetime.time": datetime.time,
}


def parse_stored(text):
    """Parse a stored Python-literal value without executing anything.

    Raises ValueError for anything that isn't plain data, matching how callers
    already handle a failed parse.
    """
    if not isinstance(text, str):
        raise ValueError(f"expected stored text, got {type(text).__name__}")
    try:
        return ast.literal_eval(text)
    except (ValueError, SyntaxError, TypeError, MemoryError, RecursionError):
        pass
    try:
        tree = ast.parse(text.strip(), mode="eval")
        return _build(tree.body)
    except (SyntaxError, RecursionError) as e:
        raise ValueError(f"stored value is not valid data: {e}") from None


def _dotted(node):
    """'datetime.date' for datetime.date; None for anything else."""
    if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
        return f"{node.value.id}.{node.attr}"
    return None


def _build(node):
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.Dict):
        if any(k is None for k in node.keys):  # {**x} unpacking
            raise ValueError("dict unpacking is not allowed in stored values")
        return {_build(k): _build(v) for k, v in zip(node.keys, node.values)}
    if isinstance(node, ast.List):
        return [_build(e) for e in node.elts]
    if isinstance(node, ast.Tuple):
        return tuple(_build(e) for e in node.elts)
    if isinstance(node, ast.Set):
        return {_build(e) for e in node.elts}
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
        operand = _build(node.operand)
        if isinstance(operand, (int, float)) and not isinstance(operand, bool):
            return -operand if isinstance(node.op, ast.USub) else operand
    if isinstance(node, ast.Call):
        ctor = _CONSTRUCTORS.get(_dotted(node.func))
        if ctor and not node.keywords:
            args = [_build(a) for a in node.args]
            if all(isinstance(a, int) and not isinstance(a, bool) for a in args):
                return ctor(*args)
    raise ValueError(f"unsupported syntax in stored value: {type(node).__name__}")
