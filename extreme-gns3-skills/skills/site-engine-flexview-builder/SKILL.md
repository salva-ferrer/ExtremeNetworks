---
name: site-engine-flexview-builder
description: Use when creating, editing, or understanding ExtremeCloud IQ Site Engine (XIQ-SE, formerly NetSight/Extreme Management Center) FlexViews (.tpl files) — building a custom SNMP table view from a MIB definition plus a natural-language description of the desired columns, deploying it and reloading the server.
---

# Building Site Engine FlexViews from a MIB

A **FlexView** is an XML definition (`.tpl`) that tells Site Engine which SNMP table to walk
and how to show each column in a grid of the UI. There is no official generator from
natural language: this skill documents the real format (DTD + examples checked on a Site
Engine 24.2.15.5) so one can be written by hand from a MIB file and a description of what
should be shown.

## Validated environment

- ExtremeCloud IQ Site Engine 24.2.15.5 running as a VM in a GNS3 lab (`site-engine-in-gns3`).
- Access to the Site Engine host by SSH (`ssh <user>@<site_engine_ip>`), `sudo` needed to read
  and write under the install directory.
- Format details below marked **confirmed** were checked against dozens of factory and
  GitHub examples; those marked **hypothesis** were not.

## Where FlexViews live

The install base is `/opt/Extreme_Networks/NetSight/` on our instance; Extreme's
documentation uses `/usr/local/Extreme_Networks/NetSight/`, and it can be chosen at install
time. **Check first**: `ls -d /opt/Extreme_Networks /usr/local/Extreme_Networks 2>/dev/null`;
if neither exists, ask the human where it is installed instead of searching blindly.
Paths below are relative to `<base>/appdata/`.

| Path | Use |
|---|---|
| `System/FlexViews/` | Loaded by the running server; organised by category (`MAC Locking/`, `Radius/`, `Interface/`...). Also has `flextable.dtd`. |
| `VendorProfiles/Released/<Vendor>/FlexViews/` | ~400 factory FlexViews (Extreme and other vendors): **example library**, do not edit. |
| **`VendorProfiles/Stage/MyVendorProfile/FlexViews/My FlexViews/`** | **Where custom FlexViews go** for Site Engine / Extreme Management Center 8.2+ (create it if missing). `System/FlexViews/My FlexViews/` was the location for NetSight ≤ 8.1. |
| `VendorProfiles/Stage/MyVendorProfile/MIBs/` | The MIB files your custom FlexViews use, so the server resolves symbolic OIDs (create if missing). |

More examples: https://github.com/extremenetworks/XMC-Report-Views (official `.tpl`
examples by category: `EXOS/`, `Networking/`, other vendors). Check it before writing one
from scratch: a similar view may exist already. Its `FlexView/README.md` documents the
path difference by version above.

## Reloading the server after adding a FlexView

Copying the file is not enough: restart the Site Engine server service as root
(per Extreme's documentation, `systemctl stop nsserver` / `systemctl start nsserver`; confirm
the unit name on your instance with `systemctl list-units | grep -i -E 'nsserver|netsight'`).
The restart interrupts the web UI: warn anyone using it first.

## XML structure (confirmed by `flextable.dtd`)

```
flextablelist
└── flextable (id=NAME, class="com.ets.nac.flexview.FvTable", ...)
    ├── tableModel          → text: com.ets.nac.tables.TbModel
    ├── column* (id, modelIndex, editable, sortOrder, width, comparator...)
    │   ├── notes?          → free text, column tooltip
    │   └── dataField       → OID reference (next section)
    ├── comments?           → general notes of the FlexView
    └── dataField?          → TBLHASH::::TBLHDR::... (base MIB table, see below)
```
All attributes of `flextable` and `column` (colours, width, order, editable...) are in the
DTD: read `<base>/appdata/System/FlexViews/flextable.dtd` for anything not covered here.

## The `dataField` of each column (partly reverse-engineered)

Format: `OID::<name-or-numeric-OID>:::SNMP::<numeric block>`. Real example:
```xml
<dataField>OID::etsysMACLockingLockedAddress:::SNMP::SNMPNA;false;4;3;false;false;4;2;0;2;6</dataField>
```
**Confirmed:**
- The OID can be symbolic (resolved against the MIBs loaded on the server) or the full
  numeric OID; both appear in factory files.
- First field = access mode: `SNMP` read-only; `SNMPW` editable (SNMP SET; always matches
  `editable="true"` on the `<column>`); `SNMPNA` hidden/not directly accessible (typically
  the row key, `hidden="true"`).

**Second field = SNMP type** (matches ASN.1/BER tags; verify against a real example of the
same type before relying on it):

| 2nd field | SNMP type | Confidence | Seen on |
|---|---|---|---|
| `2` | `INTEGER` / enum / `TruthValue` | **Confirmed** (several vendors) | `extremeImageBooted`, `ifLinkUpDownTrapEnable` |
| `3` | `BIT STRING` | Hypothesis, rare | — |
| `4` | `OCTET STRING` (binary) | Hypothesis | MAC addresses |
| `6` | `OBJECT IDENTIFIER` | Hypothesis | references to another OID |
| `15` | `DisplayString` | Strong hypothesis | `sysName`, `ifName`, `ifAlias`, firmware versions |
| `65` | `Counter32` | Hypothesis | counters |
| `66` | `Gauge32` / `Unsigned32` | Hypothesis | values going up and down |
| `67` | `TimeTicks` | **Confirmed** | `sysUpTime` |
| `70` | `Counter64` | Hypothesis | high-volume counters |

The remaining fields (column position, extra flags, trailing `0;0;0...`) are not decoded;
they seem to encode the MIB table index position and internal UI flags.

**Safest technique**: don't build the numeric block from scratch. Find, in the factory
library, an existing column whose OID has the **same SNMP `SYNTAX`** and clone its whole
block, changing only the OID name:
```bash
sudo grep -rl "Counter64" <base>/appdata/VendorProfiles/Released/ | head
```

### Reserved columns (always present)

Every FlexView starts with these 3 fixed columns, which are internal metadata, not OIDs.
Copy them as-is, with the same `id`s and order, before the real MIB columns:
```xml
<column id="0" fixed="true" hidden="true">ReqID
    <dataField>OID::ReqID:::SNMP::ReqID</dataField></column>
<column id="1" fixed="true" modelIndex="1">IP Address
    <dataField>OID::IP Address:::SNMP::IP Address</dataField></column>
<column id="2" fixed="true" hidden="true" modelIndex="2">Instance
    <dataField>OID::Instance:::SNMP::Instance</dataField></column>
```

### Computed columns (`EXPR`, advanced, use with care)

Seen in `XOS_firmware_Info.tpl` ("Device Type"): `SNMP::EXPR;true;15;3;false;false;1;2;0;0;0;0;0`
(no `OID::` prefix), plus a table-level suffix
`::::GEMHASH::::00000:Device Type::routine 111 DeviceType({ "IP Address":1 } )` calling an
internal routine. Not enough evidence to document it: clone a real `EXPR` example instead of
inventing the syntax.

### Table-level `dataField` (after the last `</column>`)

```xml
<dataField>TBLHASH::::TBLHDR::0;0;true;30;etsysMACLockingStaticStationEntry;V.0.0.2.0;0;0;106</dataField>
```
Names the **base MIB table entry** walked (`XxxEntry`, from the MIB's `SEQUENCE OF`). When
the columns come from standard tables Site Engine already knows (`ifTable`, `ifXTable`,
indexed by `ifIndex`), `None` works instead of the entry name
(`TBLHASH::::TBLHDR::0;0;true;30;None;V.0.3.3.0;0;0;103`). Name the entry explicitly only
for new proprietary tables.

## Workflow: MIB + natural-language description → `.tpl`

1. Find the target MIB table from the request and the MIB file (the `SEQUENCE OF XxxEntry`
   whose columns match).
2. For each wanted column note: OID name, `SYNTAX`, and `read-only`/`read-write`
   (`MAX-ACCESS`).
3. Look for an existing similar view (GitHub repo above, `VendorProfiles/Released/`); adapt
   it if found. Otherwise clone numeric blocks from columns of the same SNMP type.
4. Write the `.tpl`: the 3 reserved columns, one `<column>` per real OID with a `<notes>`
   describing the field in plain language, and the final `TBLHASH::::TBLHDR::` with the
   `Entry` (or `None`).
5. Put it in `VendorProfiles/Stage/MyVendorProfile/FlexViews/My FlexViews/` and the MIB in
   `VendorProfiles/Stage/MyVendorProfile/MIBs/`.
6. Restart the server service (see above).
7. Check it in the UI: device context menu → **FlexView** → it should be listed; open it on
   a device that implements the MIB and compare values with an SNMP walk (e.g. MIB Tools).

## How it reaches the browser (context only)

The `.tpl` is read by the Java backend (`FlexViewFactory`, `FvTable`, `TbModel`). The web UI
uses DWR: `/Monitor/dwr/interface/FlexViewDwr.js`, with calls such as
`FlexViewDwr.getFlexViewListByDevices(...)` and `FlexViewDwr.getTableView(query, callback)`.
The UI entry point is the device context menu item "FlexView" (`actionId: chooseFlexview`).

## Environment dependencies — what to look for in yours

| Need | What we used | What to identify in yours |
|---|---|---|
| Shell on Site Engine | SSH + `sudo` | Console or SSH access with root rights |
| MIB files | vendor MIB bundle for the firmware in use | The MIB package matching your device firmware |
