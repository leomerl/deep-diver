/** Python's hard keywords. `match` and `case` are left out: they are also ordinary variable names. */
export const KEYWORDS: ReadonlySet<string> = new Set(
  ("False None True and as assert async await break class continue def del elif else except finally for from global " +
    "if import in is lambda nonlocal not or pass raise return try while with yield").split(" "),
);

/** The builtins a notebook cell is likely to call, not the full list. */
export const BUILTINS: ReadonlySet<string> = new Set(
  ("abs all any bool bytes callable dict enumerate filter float frozenset getattr hasattr id input int isinstance " +
    "issubclass iter len list map max min next object open print range repr reversed round set setattr sorted str " +
    "sum super tuple type zip Exception KeyError RuntimeError StopIteration TypeError ValueError").split(" "),
);
