# Licenses Data

This folder contains structured metadata for each license, stored as individual JSON files.  
Each file is named using the license’s [SPDX identifier](https://spdx.org/licenses/), e.g., `MIT.json`, `Apache-2.0.json`.

## File Format

Each license file includes:
- SPDX identifier (`spdx_id`)
- License title and link to full text
- Human-readable summary
- List of standardized `rules` (see `../rules.json`)
- Optional metadata (e.g., OSI approval, FSF status, public domain status)

## File Naming

- Files must use the **exact SPDX ID** as the filename (e.g., `CC0-1.0.json`)
- One license per file

## License JSON Schema

_TBD: A machine-readable schema describing the structure of each license file will be added here._


## Related

- [`rules.json`](../rules.json): List of standardized license rules and categories (permissions, conditions, limitations)
- [SPDX License List](https://spdx.org/licenses/)
- [README.md (project root)](../../README.md)
