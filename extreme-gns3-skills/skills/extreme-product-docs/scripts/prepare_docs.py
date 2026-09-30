#!/usr/bin/env python3
"""Prepare Extreme product documentation so Claude Code can search it.

Usage:
  prepare_docs.py <docs_dir>

For every file under <docs_dir>:
  - *.zip   -> extracted next to it (once), e.g. a Site Engine "Doc Collection"
  - *.pdf   -> <same name>.txt with `pdftotext -layout` (poppler-utils), if not done yet
  - *.html  -> <same name>.txt with the HTML tags stripped
Then (re)writes <docs_dir>/INDEX.md: one row per searchable .txt with its size and a
guessed product/version/kind, for a human to correct. Nothing is ever deleted.
"""
import html
import pathlib
import re
import shutil
import subprocess
import sys
import zipfile

KINDS = [("how_to", "Knowledge article"), ("q_a", "Knowledge article"), ("command_ref", "Command Reference"), ("command reference", "Command Reference"),
         ("user_guide", "User Guide"), ("user guide", "User Guide"),
         ("release_notes", "Release Notes"), ("release notes", "Release Notes"),
         ("message_catalog", "EMS Message Catalog"), ("install", "Installation Guide"),
         ("mib", "MIB"), ("api", "API"), ("config", "Configuration Guide")]
PRODUCTS = [("switch_engine", "Switch Engine (EXOS)"), ("exos", "Switch Engine (EXOS)"),
            ("extremexos", "Switch Engine (EXOS)"), ("fabric_engine", "Fabric Engine (VOSS)"),
            ("voss", "Fabric Engine (VOSS)"), ("xiq-se", "Site Engine (XIQ-SE)"),
            ("site_engine", "Site Engine (XIQ-SE)"), ("control", "ExtremeControl"),
            ("analytics", "ExtremeAnalytics")]


def guess(name, table):
    n = name.lower().replace(" ", "_")
    for key, label in table:
        if key.replace(" ", "_") in n:
            return label
    return "?"


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    root = pathlib.Path(sys.argv[1])
    for z in sorted(root.rglob("*.zip")):
        dest = z.with_suffix("")
        if not dest.exists():
            print(f"unzip {z}")
            zipfile.ZipFile(z).extractall(dest)
    have_pdftotext = shutil.which("pdftotext") is not None
    for f in sorted(root.rglob("*")):
        txt = f.with_suffix(".txt")
        if f.suffix.lower() == ".pdf" and not txt.exists():
            if not have_pdftotext:
                print(f"skip {f}: install pdftotext (poppler-utils)")
                continue
            print(f"pdftotext {f}")
            subprocess.run(["pdftotext", "-layout", str(f), str(txt)], check=False)
        elif f.suffix.lower() in (".html", ".htm") and not txt.exists():
            raw = f.read_text(errors="replace")
            raw = re.sub(r"(?is)<(script|style).*?</\1>", " ", raw)
            text = html.unescape(re.sub(r"<[^>]+>", " ", raw))
            txt.write_text(re.sub(r"[ \t]+", " ", text))
    rows = []
    for t in sorted(root.rglob("*.txt")):
        rel = t.relative_to(root)
        ver = re.search(r"(\d+[._]\d+(?:[._]\d+){0,3})", t.name)
        rows.append(f"| `{rel}` | {guess(str(rel), PRODUCTS)} | "
                    f"{ver.group(1).replace('_', '.') if ver else '?'} | "
                    f"{guess(t.name, KINDS)} | {t.stat().st_size // 1024} KB |")
    (root / "INDEX.md").write_text(
        "# Documentation index\n\n"
        "Searchable text versions of the product documentation. Fix the guessed\n"
        "columns by hand; keep one row per document.\n\n"
        "| File | Product | Version | Kind | Size |\n|---|---|---|---|---|\n"
        + "\n".join(rows) + "\n")
    print(f"{len(rows)} documents indexed in {root / 'INDEX.md'}")


if __name__ == "__main__":
    main()
