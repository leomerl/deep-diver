import { BUILTINS, KEYWORDS } from "./pythonWords";

export type TokenKind = "comment" | "string" | "decorator" | "number" | "keyword" | "builtin" | "function" | "class";

/** `kind` is null for text that keeps the default colour. */
export type Token = { kind: TokenKind | null; text: string };

// shortcut: one regex, not a parser, so f-string fields and soft keywords stay uncoloured; switch to a real
// highlighter (CodeMirror) if the editor ever needs more than colours.
// Order matters: a `#` or a keyword inside a string must lose to the string. An unclosed string runs to the end
// of its line (or of the code, for triple quotes), which is what the reader sees while typing one.
const TOKEN = new RegExp(
  [
    /(?<comment>#.*)/,
    /(?<string>[rbfuRBFU]{0,2}(?:"""[\s\S]*?(?:"""|(?![\s\S]))|'''[\s\S]*?(?:'''|(?![\s\S]))|"(?:\\.|[^"\\\n])*"?|'(?:\\.|[^'\\\n])*'?))/,
    /(?<decorator>^[ \t]*@[\w.]+)/, // only at a line start: elsewhere `@` is the matmul operator
    /(?<number>\b\d[\w.]*)/,
    /(?<word>[A-Za-z_]\w*)/,
  ]
    .map((part) => part.source)
    .join("|"),
  "gm",
);

/** Splits Python source into coloured and plain pieces. Joining every `text` gives the source back unchanged. */
export function tokenize(code: string): Token[] {
  const tokens: Token[] = [];
  let end = 0;
  let naming: TokenKind | null = null; // set by `def` / `class`: the next word is the name being defined
  for (const match of code.matchAll(TOKEN)) {
    if (match.index > end) tokens.push({ kind: null, text: code.slice(end, match.index) });
    const { comment, string, decorator, number, word } = match.groups ?? {};
    const kind: TokenKind | null = comment
      ? "comment"
      : string
        ? "string"
        : decorator
          ? "decorator"
          : number
            ? "number"
            : (naming ?? (KEYWORDS.has(word ?? "") ? "keyword" : BUILTINS.has(word ?? "") ? "builtin" : null));
    tokens.push({ kind, text: match[0] });
    naming = word === "def" ? "function" : word === "class" ? "class" : null;
    end = match.index + match[0].length;
  }
  return end < code.length ? [...tokens, { kind: null, text: code.slice(end) }] : tokens;
}
