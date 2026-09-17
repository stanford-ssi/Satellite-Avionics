# Kicad Libraries
This folder is where you will find the actual files you must include in your KiCad projects in order to easily integrate ICs and other components into your designs without having to endlessly search for a pre-existing footprint. We develop the schematic, footprint, and routing for each of these components ourselves in order to keep standardization across all our work. 
## SSI_Passives — approved passive components (database library)
[`SSI_Passives/`](SSI_Passives/) is a KiCad **database library** holding every LCSC/JLCPCB part of the
resistor, capacitor and inductor series approved in the Component Library & Standards Guide, grouped
into Basic (no JLCPCB fee) / Extended sub-libraries plus Flight series. One-time setup (SQLite ODBC
driver + two library-table rows) and maintenance instructions are in its [README](SSI_Passives/README.md).
