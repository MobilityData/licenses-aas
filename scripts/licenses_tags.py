#!/usr/bin/env python
#!/usr/bin/env python
"""
licenses_tags.py

This script applies tag heuristics to license JSON files in the `data/licenses/` directory.
Tags provide metadata about licenses, such as their permissions, restrictions, and domains
of applicability. The script validates tags against a tag registry (`data/tags.json`) and
updates the `tags` field in each license JSON file.

Usage:
    python licenses_tags.py [--only-missing]

Options:
    --only-missing    Only add tags to files that do not already have a `tags` field.

Features:
- **Tag Generation**: Automatically generates tags for licenses based on their SPDX ID and metadata.
- **Validation**: Ensures generated tags are valid according to the tag registry.
- **Heuristics**: Applies predefined rules to assign tags based on license characteristics.

Tagging Categories:
- **License Type**: e.g., `license:public-domain`, `license:open-source`, `license:creative-commons`.
- **Domain**: e.g., `domain:content`, `domain:data`, `domain:software`.
- **Copyleft Strength**: e.g., `copyleft:none`, `copyleft:weak`, `copyleft:strong`.
- **Family**: e.g., `family:CC` (Creative Commons), `family:GPL` (GNU General Public License).
- **Notes**: e.g., `notes:attribution-required`, `notes:share-alike`.

Dependencies:
- Python 3.8+
- `data/tags.json`: The tag registry file containing valid tags and their metadata.

Examples:
1. Apply tags to all license files:
    python licenses_tags.py

2. Apply tags only to files missing the `tags` field:
    python licenses_tags.py --only-missing

Notes:
- Public domain licenses (e.g., `CC0-1.0`, `UNLICENSE`) are tagged as `license:public-domain` and apply to both `domain:content` and `domain:data`.
- Creative Commons licenses (e.g., `CC-BY-4.0`) are tagged as `license:creative-commons` and may include additional notes like `notes:attribution-required` or `notes:share-alike`.
- Open Data Commons licenses (e.g., `ODBL`, `PDDL`) are tagged as `license:open-data-commons` and focus on `domain:data`.

"""
import json
import argparse
from pathlib import Path
from typing import Dict, Any, List, Optional

BASE_DIR = Path(__file__).resolve().parent.parent

LICENSES_DIR = BASE_DIR / "data" / "licenses"
TAGS_JSON_PATH = BASE_DIR / "data" / "tags.json"


# ---------- Tag Registry ----------

class TagRegistry:
    """
    Loads the tag registry (data/tags.json) and validates tag keys of the form 'group:key'.

    Each group (e.g. 'license', 'domain') can contain:
      - a special '_group' entry with {short, description}
      - tag keys (e.g. 'creative-commons') with {description, url}
    """

    def __init__(self, path: Path):
        with path.open("r", encoding="utf-8") as f:
            self.registry: Dict[str, Dict[str, Any]] = json.load(f)

    def is_valid(self, tag: str) -> bool:
        group, _, key = tag.partition(":")
        if not group or not key:
            return False
        group_dict = self.registry.get(group)
        if not isinstance(group_dict, dict):
            return False
        # '_group' is reserved metadata, not an actual tag key
        if key == "_group":
            return False
        return key in group_dict

    def get_group_meta(self, group: str) -> Optional[Dict[str, Any]]:
        """
        Return the metadata (short, description) for a tag group, if available.
        Useful for UI rendering.
        """
        group_dict = self.registry.get(group)
        if not isinstance(group_dict, dict):
            return None
        meta = group_dict.get("_group")
        if isinstance(meta, dict):
            return meta
        return None

    def get_tag_info(self, tag: str) -> Optional[Dict[str, Any]]:
        """
        Return the full info for a specific tag (description, url) if it exists.
        """
        group, _, key = tag.partition(":")
        group_dict = self.registry.get(group)
        if not isinstance(group_dict, dict):
            return None
        info = group_dict.get(key)
        if isinstance(info, dict):
            return info
        return None


# ---------- Tag Heuristics ----------

def build_tags(spdx_id: str, spdx_info: Dict[str, Any]) -> List[str]:
    """
    Build raw tag list (strings) for a given SPDX ID using heuristics.
    A license MAY receive multiple tags from the same group
    (for example domain:content AND domain:data).
    Validation against TagRegistry is done separately.
    """
    tags: List[str] = []
    sid = spdx_id.upper()

    osi = bool(spdx_info.get("isOsiApproved"))
    fsf = bool(spdx_info.get("isFsfLibre"))
    deprecated = bool(spdx_info.get("isDeprecatedLicenseId"))

    # SPDX status tags
    if osi:
        tags.append("spdx:osi-approved")
    if fsf:
        tags.append("spdx:fsf-free")
    if deprecated:
        tags.append("spdx:deprecated")

    # --- Public domain / PD-like licenses ---
    # These can be safely used for BOTH content and data,
    # and have no copyleft obligations at all.
    PUBLIC_DOMAIN = {"CC0-1.0", "UNLICENSE", "0BSD"}
    if sid in PUBLIC_DOMAIN:
        tags += [
            "license:public-domain",
            "copyleft:none",
            "domain:content",
            "domain:data",
        ]
        return tags

    # --- Creative Commons ---
    if sid.startswith("CC-"):
        tags += [
            "license:creative-commons",
            "family:CC",
            "domain:content",  # CC is content-first by design
        ]

        # Attribution + ShareAlike notes
        if "-BY-" in sid:
            tags.append("notes:attribution-required")
        if "-SA-" in sid:
            tags.append("notes:share-alike")

        # CC-BY / CC-BY-SA 4.0 are widely used for data as well.
        # We allow dual-domain tagging here.
        if sid.startswith(("CC-BY-", "CC-BY-SA-")) and sid.endswith("-4.0"):
            tags.append("domain:data")

        return tags

    # --- Open Data Commons (data-focused) ---
    if sid.startswith(("ODBL", "ODC-", "PDDL")):
        tags += [
            "license:open-data-commons",
            "family:ODC",
            "domain:data",
        ]
        # ODbL and ODC-By strongly encourage attribution and share-alike
        if sid.startswith(("ODBL", "ODC-BY")):
            tags.append("notes:attribution-required")
            tags.append("notes:share-alike")
        # PDDL is public-domain-like for data, but we still treat it as data-centric
        return tags

    # --- Government open licenses ---
    if sid.startswith(("OGL-", "NLOD-", "ETALAB-")):
        # Government open licenses often cover BOTH published reports (content)
        # and open data files (data), so we tag them as dual-domain.
        tags += [
            "license:government-open-license",
            "domain:data",
            "domain:content",
            "notes:government-open-license",
            "notes:attribution-required",
        ]
        return tags

    # --- GPL family ---
    if sid.startswith("GPL-"):
        tags += [
            "license:open-source",
            "family:GPL",
            "domain:software",
            "copyleft:strong",
        ]
        return tags

    # --- AGPL ---
    if sid.startswith("AGPL-"):
        tags += [
            "license:open-source",
            "family:AGPL",
            "domain:software",
            "copyleft:network",
        ]
        return tags

    # --- LGPL ---
    if sid.startswith("LGPL-"):
        tags += [
            "license:open-source",
            "family:LGPL",
            "domain:software",
            "copyleft:weak",
        ]
        return tags

    # --- Weak copyleft: MPL, EPL, CDDL ---
    if sid.startswith(("MPL-", "EPL-", "CDDL-")):
        tags += [
            "license:open-source",
            "domain:software",
            "copyleft:weak",
        ]
        return tags

    # --- Documentation-oriented licenses (GFDL etc.) ---
    if sid.startswith("GFDL-"):
        # GFDL is mainly for documentation / manuals,
        # but that content is still expressive content.
        tags += [
            "license:open-source",
            "domain:documentation",
            "domain:content",
        ]
        return tags

    # --- Permissive licenses: MIT, BSD, Apache, ISC, Zlib ---
    if sid.startswith(("MIT", "BSD-", "APACHE-", "ISC", "ZLIB")):
        tags += [
            "license:open-source",
            "domain:software",
            "copyleft:permissive",
        ]
        return tags

    # --- Default fallback for unknown OSS-y licenses ---
    tags += [
        "license:open-source",
        "domain:software",
    ]
    return tags


def apply_tags_to_file(path: Path, registry: TagRegistry) -> None:
    """
    Load a single license JSON file, compute tags, and update the "tags" field.
    Does not modify any other keys.
    """
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    spdx_info = data.get("spdx")
    if not isinstance(spdx_info, dict):
        # Nothing to do if SPDX info isn't present
        return

    spdx_id = spdx_info.get("licenseId")
    if not spdx_id:
        return

    raw_tags = build_tags(spdx_id, spdx_info)
    valid_tags = [t for t in raw_tags if registry.is_valid(t)]

    data["tags"] = valid_tags

    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


# ---------- CLI ----------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Apply tag heuristics to merged license JSON files (data/licenses/*.json)."
    )
    parser.add_argument(
        "--only-missing",
        action="store_true",
        help="Only add tags to files that do not already have a 'tags' field.",
    )
    args = parser.parse_args()

    if not TAGS_JSON_PATH.exists():
        raise FileNotFoundError(f"Tag registry not found at {TAGS_JSON_PATH}")

    registry = TagRegistry(TAGS_JSON_PATH)

    for json_file in sorted(LICENSES_DIR.glob("*.json")):
        if args.only_missing:
            with json_file.open("r", encoding="utf-8") as f:
                try:
                    data = json.load(f)
                except json.JSONDecodeError:
                    continue
            if "tags" in data:
                # Skip files that already have tags
                continue

        apply_tags_to_file(json_file, registry)


if __name__ == "__main__":
    main()
