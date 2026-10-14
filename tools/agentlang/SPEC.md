# Tongue v0: write a patch as sentences

SPEC size: 4080 characters (limit 7000).

You edit an Infinite patch with short sentences, one per line. A blank line ends a paragraph.
A paragraph is all-or-nothing: if any sentence fails, none is applied. Sentences become `.inf` text.

## The seven verbs

| Sentence | Meaning |
|---|---|
| `ask <type>` | Look up a node type: its input slots, outputs and saved keys. Read-only. |
| `add <type> as <name>` | New node. `<type>` is the exact type name and may contain spaces. |
| `set <name>.<key> <value>` | Set one saved key. The value is the rest of the line. |
| `wire <src> <dst>[.<slot>]` | Connect the output of `src` to an input slot of `dst`. |
| `cut <src> <dst>[.<slot>]` | Remove that connection. |
| `del <name>` | Remove a node and every connection to it. |
| `field <name> <code>` | Set the `code` key of a Field node to the rest of the line, verbatim. |

Examples:

```
ask Blend
add Shape as a
add gaussianblur as soft
set soft.uRadius 6
set a.shapeType Star
wire a soft
wire soft out.in
cut a out.in
del a
field fp col = vec3(uv.x, uv.x, uv.x);
```

## Names and slots

- A name is a word you choose in `add ... as <name>`, an `id` already in the patch, or a node
  number from the patch (`3`). A name has no spaces and no dot.
- `wire` always reads source first: `wire shape out.in` feeds `shape` into the `in` slot of `out`.
- `.slot` is a slot name from `ask` (`in`, `input`, `input_2`, `audio`, `notes`, `geo_a`, `camera`).
  Leave it out only when the destination has exactly one input slot; otherwise it is `E_SEM`.
- A wire must carry a kind the slot accepts (image to image, audio to audio, notes to notes,
  geometry to geometry). An input slot takes one wire.

## Values

- Numbers have no trailing zeros: `0.5`, `6`, `440`. No `+`, no units, no `%`.
- A choice (shape, waveform, mode) is its option name as one word: `Star`, `Sine`.
- A colour is `r g b` or `r g b a`. A switch is `0` or `1`.
- Anything else is text to the end of the line.

## Field

`field <name> <code>` takes Field source as is. Bare names, no sigils (`P.y += sin(P.x + t) * 0.2`).
`;` separates statements on one line. Do not write `#` in a `field` sentence (it is rejected).
Whether the code compiles is checked later by `--validate`, not by the sentence checker.

A kernel only knows the names of its node's domain; any other name is `E_FIELD` ("used before assignment").

| Node | Names you may read | Writes |
|---|---|---|
| Field Pixel | `uv xy res aspect t dt frame age` | `col` (and `alpha`) |
| Field Synth | `freq gate sr n t` | `out` |
| Field Effect | `in sr n` | `out` |
| Field Modifier | `P N uv Cd i count t` | `P N Cd` |

`t` is frame time and is not a sample-domain clock. For a sine voice use
`field v out = sin(6.2831853 * n * freq / sr) * 0.5 * gate`; for a running phase keep it in a cell:
`field v state float ph = 0; ph = ph + freq / sr; out = sin(6.2831853 * ph) * 0.5 * gate`.

## Replies

The reply is `{ok, errors:[...]}` and carries only the first error:
`{"ok":false,"errors":[{"code":"E_SEM","level":3,"line":2,"hint":"..."}]}`

| Code | Level | Cause | Hint carries |
|---|---|---|---|
| `E_LEX` | 1 | a word that is not a verb or node type | the 3 nearest words |
| `E_SYN` | 2 | wrong number or kind of arguments | the verb's signature |
| `E_SEM` | 3 | unknown name, key or slot, value out of range, illegal wire | the valid choices, or min, max and current |
| `E_FIELD` | 4 | Field code does not compile | the compiler message; only `--validate` sees it |

When `ok` is true the reply also says `checked_by: "--validate"` for what the sentence checker cannot see.

## Rules

- One spelling per operation. Unknown words are errors, never guessed.
- Names given by `add` exist only after their sentence; use them in later sentences.
- Out of scope in v0: modulation, expressions, globals, clips, flags. Use `.inf` for those.
- Layout and `Comment` nodes are not written; positions are added afterwards.
- Something must reach an `Output` (picture) or `Audio Out` (sound), or the patch shows nothing.
