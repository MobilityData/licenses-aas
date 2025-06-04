## License Merge Utility

### `merge_spdx_with_choosealicense.py`

This script merges license metadata from the [SPDX license-list-data](https://github.com/spdx/license-list-data) and [choosealicense.com](https://github.com/github/choosealicense.com) datasets. It outputs one JSON file per license in the `data/licenses/` folder.

### Output

Each output file is named using the SPDX ID (e.g., `MIT.json`) and contains:

- `spdx`: SPDX license metadata
- `categorized`: `true` if the license was categorized by merging with an external source or manually available, otherwise `false`
- `permissions`: list of granted permissions
- `conditions`: list of conditions that must be met
- `limitations`: list of limitations and restrictions

### Usage

```bash
python merge_spdx_with_choosealicense.py
```

#### Options

| Flag                    | Description                                        |
|-------------------------|----------------------------------------------------|
| `--update-submodules`   | Pull the latest data from git submodules           |
| `--only-uncategorized`  | Export only licenses that are not categorized      |

#### Example

```bash
python merge_spdx_with_choosealicense.py --update-submodules --only-uncategorized
```

---

## License Inspector CLI

### `inspect_licenses.py`

A command-line utility to explore the merged SPDX license metadata.

### Usage

```bash
python inspect_licenses.py <command> [options]
```

### Commands

#### `count`

Show totals for all licenses, categorized and uncategorized.

```bash
python inspect_licenses.py count
```

#### `list`

List all license SPDX IDs.

```bash
python inspect_licenses.py list
```

**Options**:

- `--only-categorized`: list only categorized licenses  
- `--only-uncategorized`: list only uncategorized licenses

#### `summary`

Show a summary grouped by categorized status.

```bash
python inspect_licenses.py summary
```

#### `get`

Show metadata for a single license by SPDX ID (case-insensitive).

```bash
python inspect_licenses.py get mit
```

Outputs:

- SPDX ID
- Permissions
- Conditions
- Limitations

---

### Dependencies

Install the required Python packages:

```bash
pip install -r requirements.txt
```
