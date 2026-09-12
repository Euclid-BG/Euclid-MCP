# LSP-euclid

[LSP](https://github.com/sublimelsp/LSP) client plugin for
[Euclid-IR](https://github.com/Euclid-BG/Euclid-MCP) — deterministic logical
reasoning via Prolog.

## Features

- **Diagnostics** — parse errors, undefined predicates, circular rules
- **Autocomplete** — predicate names, keywords, operators
- **Hover** — predicate info with fact/rule counts
- **Syntax highlighting** — keywords, variables, strings, comments

## Installation

### Prerequisites

Install the language server:

```bash
pip install euclid-lsp
# or from source:
uv pip install -e /path/to/Euclid-MCP/euclid-lsp
```

### Via Package Control

1. Open Command Palette → `Package Control: Install Package`
2. Search for **LSP-euclid**
3. Install

### Manual installation

1. Clone this repository into your Sublime Text `Packages/User/` directory:

```bash
cd ~/.config/sublime-text/Packages/User  # Linux
# or ~/Library/Application Support/Sublime Text/Packages/User  # macOS
git clone https://github.com/Euclid-BG/Euclid-MCP.git LSP-euclid
```

2. Restart Sublime Text

### Via LSP settings

If you prefer not to install a separate package, add this to
`Preferences → Package Settings → LSP → Server Configurations`:

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

## Syntax highlighting

This package includes a `.tmLanguage` syntax definition. If it doesn't
activate automatically, manually assign it:

1. Open a `.euclid` file
2. Click the language name in the bottom-right corner
3. Select **Euclid-IR**

## License

Apache-2.0
