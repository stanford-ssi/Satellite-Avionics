# Component Library

**Note: THIS IS ONLY OUR COMPONENT LIBRARY, NOT A SELECTION GUIDE, IF YOU NEED HELP DECIDING WHAT COMPONENTS TO SELECT, PLEASE SEE THE OFFICIAL AV [COMPONENT SELECTION](https://gitlab.com/ssi-satellite-avionics/design-guide-and-team-standards/-/tree/main/Design_Standards/Component_Selection?ref_type=heads) GUIDE.**

This repository is your one-stop-shop for all your component library needs. This repository is separated into two distinct foloder:

### [Datasheets and Docs](./datasheets-and-docs)
 - This folder is where you will find the datasheets for every IC we have found and or researched. Keep in mind that these are not components we have cleared to use in designs and are not guaranteed to work within the Low-Earth-Orbit (LEO) temperature and rad-tolerance requirement set by our team as per our [Design Guide and Team Standards](https://gitlab.com/ssi-satellite-avionics/design-guide-and-team-standards).

### [KiCad Libraries](./kicad-libraries)
 - This folder is where you will find the actual files you must include in your KiCad projects in order to easily integrate ICs and other components into your designs without having to endlessly search for a pre-existing footprint. We develop the schematic, footprint, and routing for each of these components ourselves in order to keep standardization across all our work. Please consult the [Design Guide and Team Standards](https://gitlab.com/ssi-satellite-avionics/design-guide-and-team-standards) repository prior to adding to these libraries to understand how to properly create a component template.
