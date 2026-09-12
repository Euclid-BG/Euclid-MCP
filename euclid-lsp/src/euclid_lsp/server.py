"""Euclid-IR LSP server — main entry point using pygls."""

from __future__ import annotations

import logging

from euclid_mcp.validation import run_check_kb
from lsprotocol import types
from pygls.lsp.server import LanguageServer
from pygls.workspace import TextDocument

from euclid_lsp.autocomplete import compute_completions
from euclid_lsp.diagnostics import compute_diagnostics
from euclid_lsp.hover import compute_hover
from euclid_lsp.positioned_parser import PositionedKB, parse_positioned

logger = logging.getLogger("euclid-lsp")

# Document cache: uri -> (version, positioned_kb)
_doc_cache: dict[str, tuple[int, PositionedKB]] = {}


class EuclidLanguageServer(LanguageServer):
    """Language server for Euclid-IR files."""

    def __init__(self) -> None:
        super().__init__(
            name="euclid-lsp",
            version="0.5.0",
        )


_server = EuclidLanguageServer()


def _get_pkb(doc: TextDocument) -> PositionedKB:
    """Get or compute the positioned KB for a document."""
    uri = doc.uri
    version = doc.version or 0
    cached = _doc_cache.get(uri)
    if cached and cached[0] == version:
        return cached[1]

    text = doc.source
    pkb = parse_positioned(text)
    _doc_cache[uri] = (version, pkb)
    return pkb


def _publish_diagnostics(uri: str, diagnostics: list[types.Diagnostic]) -> None:
    """Publish diagnostics for a document."""
    _server.text_document_publish_diagnostics(
        types.PublishDiagnosticsParams(
            uri=uri,
            diagnostics=diagnostics,
        )
    )


def _run_diagnostics(doc: TextDocument) -> None:
    """Validate the document and publish diagnostics."""
    text = doc.source
    pkb = _get_pkb(doc)

    result = run_check_kb(text)

    errors = [e.model_dump() for e in result.errors]
    warnings = [w.model_dump() for w in result.warnings]

    diagnostics = compute_diagnostics(pkb, errors, warnings)
    _publish_diagnostics(doc.uri, diagnostics)


@_server.feature("textDocument/didOpen")
def did_open(params: types.DidOpenTextDocumentParams) -> None:
    """Handle document open: run initial diagnostics."""
    doc = _server.workspace.get_text_document(params.text_document.uri)
    _run_diagnostics(doc)


@_server.feature("textDocument/didChange")
def did_change(params: types.DidChangeTextDocumentParams) -> None:
    """Handle document change: re-run diagnostics."""
    doc = _server.workspace.get_text_document(params.text_document.uri)
    _run_diagnostics(doc)


@_server.feature("textDocument/didSave")
def did_save(params: types.DidSaveTextDocumentParams) -> None:
    """Handle document save: re-run diagnostics."""
    doc = _server.workspace.get_text_document(params.text_document.uri)
    _run_diagnostics(doc)


@_server.feature("textDocument/didClose")
def did_close(params: types.DidCloseTextDocumentParams) -> None:
    """Handle document close: clear cache and diagnostics."""
    uri = params.text_document.uri
    _doc_cache.pop(uri, None)
    _publish_diagnostics(uri, [])


@_server.feature("textDocument/completion")
def completion(params: types.CompletionParams) -> list[types.CompletionItem]:
    """Provide completion items."""
    doc = _server.workspace.get_text_document(params.text_document.uri)
    pkb = _get_pkb(doc)
    position = params.position
    lines = doc.source.split("\n")
    line_text = lines[position.line] if position.line < len(lines) else ""
    return compute_completions(pkb, line_text, position.character)


@_server.feature("textDocument/hover")
def hover(params: types.HoverParams) -> types.Hover | None:
    """Provide hover information."""
    doc = _server.workspace.get_text_document(params.text_document.uri)
    pkb = _get_pkb(doc)
    return compute_hover(pkb, params.position.line, params.position.character)


def main() -> None:
    """Entry point for euclid-lsp."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
    logger.info("Starting Euclid-IR LSP server")
    _server.start_io()


if __name__ == "__main__":
    main()
