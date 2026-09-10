# Component Library

This repository is your one-stop-shop for all your component library needs. This repository is separated into two distinct foloder:

### [Datasheets and Docs](./datasheets-and-docs)
 - This folder is where you will find the datasheets for every IC we have found and or researched. Keep in mind that these are not components we have cleared to use in designs and are not guaranteed to work within the Low-Earth-Orbit (LEO) temperature and rad-tolerance requirement set by our team as per our [Design Guide and Team Standards](https://gitlab.com/ssi-satellite-avionics/design-guide-and-team-standards).

### [KiCad Libraries](./kicad-libraries)
 - This folder is where you will find the actual files you must include in your KiCad projects in order to easily integrate ICs and other components into your designs without having to endlessly search for a pre-existing footprint. We develop the schematic, footprint, and routing for each of these components ourselves in order to keep standardization across all our work. Please consult the [Design Guide and Team Standards](https://gitlab.com/ssi-satellite-avionics/design-guide-and-team-standards) repository prior to adding to these libraries to understand how to properly create a component template.
