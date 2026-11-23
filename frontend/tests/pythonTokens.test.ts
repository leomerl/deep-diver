import { expect, test } from "vitest";

import { tokenize } from "../src/pythonTokens";

const coloured = (code: string) => tokenize(code).filter((token) => token.kind).map((token) => [token.kind, token.text]);

test("joining the tokens gives the source back", () => {
  const code = 'import re\n\n@cache\ndef f(x: int) -> str:\n    """doc # not a comment"""\n    return f"{x}" * 0x1f  # done\n';
  expect(tokenize(code).map((token) => token.text).join("")).toBe(code);
});

test("names a function and a class after def and class", () => {
  expect(coloured("class Lease:\n    def renew(self): pass")).toEqual([
    ["keyword", "class"],
    ["class", "Lease"],
    ["keyword", "def"],
    ["function", "renew"],
    ["keyword", "pass"],
  ]);
});

test("a string hides the keywords and the hash inside it", () => {
  expect(coloured("x = 'if # no' # yes")).toEqual([
    ["string", "'if # no'"],
    ["comment", "# yes"],
  ]);
});

test("an unclosed triple-quoted string runs to the end", () => {
  expect(coloured('"""a\nfor')).toEqual([["string", '"""a\nfor']]);
});

test("colours builtins, numbers and decorators, but not matmul", () => {
  expect(coloured("@app.get\nprint(len(a) @ 1_000)")).toEqual([
    ["decorator", "@app.get"],
    ["builtin", "print"],
    ["builtin", "len"],
    ["number", "1_000"],
  ]);
});
