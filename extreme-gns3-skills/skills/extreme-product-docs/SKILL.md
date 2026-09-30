---
name: extreme-product-docs
description: Use when the user provides (or should provide) Extreme Networks product documentation — Switch Engine/Fabric Engine User Guides, Command References, EMS message catalogs, Site Engine doc collections, release notes, knowledge articles, MIBs — and whenever a CLI syntax, default, log message or feature limit must be confirmed before configuring a switch or Site Engine. Covers preparing the docs folder for search and the rules for using it.
---

# Using Extreme product documentation as a reference

Claude's built-in knowledge of Extreme CLIs is not version-exact, and the documentation
itself sometimes disagrees with the firmware. The reliable method: give Claude the official
documents **for the exact versions in the lab**, as searchable text, and verify against the
live CLI.

## Validated environment

- Linux, `pdftotext` (poppler-utils) and Python 3. Used with the Switch Engine 33.1.1 User
  Guide, Command References and EMS Message Catalog, and a Site Engine documentation
  collection (zip), while configuring and debugging EXOS switches and UPM/Python scripts.

## 1. What to provide

Download from the Extreme documentation portal the documents matching the **firmware and
software versions in your lab** (`show version` / `show sys-info` / Site Engine "About"):

| Product | Most useful documents |
|---|---|
| Switch Engine (EXOS) | Command References, User Guide, EMS Message Catalog, Release Notes |
| Fabric Engine (VOSS) | Command Reference, Configuration guides (by feature area), Release Notes |
| Site Engine (XIQ-SE) | Documentation collection (zip): User Guide, Installation Guide, API docs, Release Notes |
| ExtremeControl / ExtremeAnalytics | Installation and User Guides of the engine version |
| Any | Knowledge articles (save the page as HTML), vendor MIB bundle for the firmware |

## 2. Prepare the folder

Put everything in a `docs/` folder of the project (original PDFs/zips/HTML) and run:
```bash
python3 scripts/prepare_docs.py docs/
```
It unzips collections, converts each PDF with `pdftotext -layout` and each HTML page to
`.txt` next to the original, and writes `docs/INDEX.md` (file, product, version, kind, size)
with guessed values: **correct the product/version columns by hand**, since the version is
what makes a document trustworthy for a given switch. Re-running only processes new files.
Large documents are fine (a Command Reference is ~8 MB of text): they are searched, not
read whole.

Tell Claude in the project's `CLAUDE.md` (or at the start of the session) that the folder
exists, e.g.: "Official docs for the lab versions are in `docs/`, index in
`docs/INDEX.md`. Check syntax there before configuring."

## 3. Rules for using it (for Claude)

1. **Before stating or sending a command you are not certain of, search the matching
   document**: `grep -n -i "<command words>" docs/<command reference>.txt`, then read the
   section around the hit (`sed -n '<from>,<to>p'`): syntax, defaults, usage guidelines,
   platform notes.
2. **Match versions**: use the document of the version running on the device; say so when
   only another version's document is available.
3. **The live CLI wins**: confirm with `?` / tab completion on the device (in a test
   node, not on a node someone is using). When the document and the firmware disagree,
   follow the device, and record the discrepancy (e.g. in `docs/DISCREPANCIES.md`) so it
   isn't rediscovered.
4. **Logs**: look up unknown log messages in the EMS Message Catalog (message name, meaning,
   severity) before guessing their cause.
5. Cite what you used: "Command Reference 33.1.1, `enable dhcp vlan`, p. 2218", so a human can
   check it.
6. Quote only what's needed; don't paste large parts of the documents into chats, tickets or
   public posts (they are copyrighted).

Worked example: lab notes said `enable dhcp ipv4 vlan <name>`; the 33.1.1 Command Reference
gives `enable dhcp [ipv4 | ipv6] [vlan_name | all]` (IPv4 is the default when omitted). Both
agree, and the device accepted it, so it goes into the skill as confirmed.

## Environment dependencies — what to look for in yours

| Need | What we used | What to identify in yours |
|---|---|---|
| PDF to text | `pdftotext` (poppler-utils) | poppler for your OS, or any PDF-to-text tool keeping the layout |
| Search | `grep` | Any text search tool Claude Code can run |
| Documents | Extreme documentation portal | Access to the portal for your versions |
