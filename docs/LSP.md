# Euclid-IR Language Server (LSP)

Real-time diagnostics, autocomplete, and hover for `.euclid` files.

## Quick start — VS Code

VS Code is the primary target. Two steps:

### 1. Install the LSP server

```bash
# From the repo root (with active virtualenv)
uv pip install -e euclid-lsp
```

Verify:

```bash
euclid-lsp --help   # should start then exit (stdio mode)
```

### 2. Install the VS Code extension

Open the extension folder as a workspace:

```
File → Open Folder → euclid-lsp/vscode/
```

Then press `F5` to launch the **Extension Development Host** (a second
VS Code window with the extension loaded). Open any `.euclid` file in
that window — diagnostics appear automatically.

To install permanently (without F5):

```bash
code --install-extension euclid-lsp/vscode/
```

### What you get

| Feature | Trigger | Description |
|---|---|---|
| **Diagnostics** | On open / change / save | Parse errors, undefined predicates, circular rules, duplicate facts |
| **Autocomplete** | `Ctrl+Space` or while typing | Predicate names, keywords (`if`, `and`, `not`), operators, rule snippet |
| **Hover** | Mouse over predicate | Fact/rule counts, rule IDs |
| **Syntax highlighting** | Automatic | Keywords, variables, strings, comments, operators |
| **Folding** | `Ctrl+Shift+[` | Collapse rule bodies |

### Configuration

In VS Code Settings (`Ctrl+,`):

```jsonc
{
  // Path to the LSP server (default: "euclid-lsp" on PATH)
  "euclid.serverPath": "euclid-lsp",

  // Trace LSP communication (for debugging)
  "euclid.trace.server": "verbose"
}
```

## Other editors

The LSP server is editor-agnostic. Any editor that speaks the Language
Server Protocol can use it.

### Neovim (built-in LSP)

Add to your `init.lua`:

```lua
vim.lsp.config.euclid = {
  cmd = { "euclid-lsp" },
  filetypes = { "euclid" },
  root_markers = { ".git" },
}
vim.lsp.enable("euclid")

vim.filetype.add({ extension = { euclid = "euclid" } })
vim.treesitter.language.register("euclid", "euclid")
```

### Vim (via coc.nvim)

Add to `coc-settings.json` (`:CocConfig`):

```json
{
  "languageserver": {
    "euclid": {
      "command": "euclid-lsp",
      "filetypes": ["euclid"]
    }
  }
}
```

### Emacs (lsp-mode)

```elisp
(lsp-register-client
 (make-lsp-client :new-connection (lsp-stdio-connection "euclid-lsp")
                  :major-modes '(euclid-mode)
                  :server-id 'euclid-lsp))

(add-to-list 'lsp-language-id-configuration '(euclid-mode . "euclid"))
```

### Sublime Text (LSP plugin)

Install the [LSP](https://packagecontrol.io/packages/LSP) package,
then install **LSP-euclid** from Package Control. It provides syntax
highlighting and LSP integration out of the box.

Manual install — clone into your Packages directory:

```bash
cd ~/.config/sublime-text/Packages/User  # Linux
# or ~/Library/Application Support/Sublime Text/Packages/User  # macOS
git clone https://github.com/Euclid-BG/Euclid-MCP.git LSP-euclid
```

Or add to `Preferences → Package Settings → LSP → Server Configurations`:

```json
{
  "clients": {
    "LSP-euclid": {
      "enabled": true,
      "command": ["euclid-lsp"],
      "selector": "source.euclid"
    }
  }
}
```

### Zed

Add to `~/.config/zed/settings.json`:

```json
{
  "languages": {
    "Euclid-IR": {
      "autolocate_server": {
        "command": "euclid-lsp"
      }
    }
  }
}
```

### Helix

Add to `~/.config/helix/languages.toml`:

```toml
[[language]]
name = "euclid"
language-servers = ["euclid-lsp"]

[language-server.euclid-lsp]
command = "euclid-lsp"
```

### OpenCode

OpenCode supports custom LSP servers. Add to `opencode.json` in your
project root:

```json
{
  "$schema": "https://opencode.ai/config.json",
  "lsp": {
    "euclid": {
      "command": ["euclid-lsp"],
      "extensions": [".euclid"]
    }
  }
}
```

OpenCode will automatically start the LSP server when a `.euclid` file
is opened, and feed diagnostics back into the agent loop. See the
[OpenCode LSP docs](https://opencode.ai/docs/lsp/) for details.

## Troubleshooting

**No diagnostics appear**
- Check that `euclid-lsp` is on PATH: `which euclid-lsp`
- Check the Output panel → "Euclid-IR Language Server"
- Set `"euclid.trace.server": "verbose"` in VS Code settings

**Autocomplete shows no predicates**
- The KB must be parsed successfully for predicates to appear
- Check diagnostics for parse errors first

**Hover shows "No definitions found"**
- The cursor must be on a predicate name followed by `(`
- Hover does not trigger on variables or operators

## Architecture

```
euclid-lsp/
├── src/euclid_lsp/
│   ├── server.py              # pygls entry point (stdio)
│   ├── positioned_parser.py   # wraps language.py with line/col
│   ├── diagnostics.py         # errors/warnings → LSP Diagnostic
│   ├── autocomplete.py        # CompletionItem generation
│   └── hover.py               # Hover information
├── vscode/
│   ├── package.json           # VS Code extension manifest
│   ├── extension.js           # LSP client
│   ├── language-configuration.json
│   └── syntaxes/euclid.tmLanguage.json
└── tests/                     # pytest suite
```

The LSP server imports `euclid_mcp.validation.run_check_kb` — the same
validation logic used by the MCP server and CLI. No duplication.
