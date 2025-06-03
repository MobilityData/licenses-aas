import os
import json
import yaml
import argparse
import subprocess
from pathlib import Path
import pandas as pd

# Define paths for submodules
BASE_DIR = Path(__file__).resolve().parent.parent
SPDX_JSON_DIR = BASE_DIR / "data/spdx/details"
CHOOSEALICENSE_DIR = BASE_DIR / "data/choosealicense"
MERGED_DIR = BASE_DIR / "data/licenses"
MERGED_DIR.mkdir(parents=True, exist_ok=True)

def update_submodules():
    subprocess.run(["git", "submodule", "update", "--init", "--recursive"], check=True)
    subprocess.run(["git", "submodule", "update", "--remote", "--merge"], check=True)

def load_spdx_licenses(spdx_dir):
    """
    Load SPDX licenses
    :return:
    """
    licenses = {}
    for json_file in spdx_dir.glob("*.json"):
        with open(json_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            licenses[data["licenseId"]] = data
    return licenses

def load_choosealicense_metadata(choosealicense_dir):
    """
    Load ChooseALicense metadata
    """
    licenses = {}
    for md_file in choosealicense_dir.glob("*.txt"):
        with open(md_file, "r", encoding="utf-8") as f:
            content = f.read()
            if content.startswith("---"):
                front_matter = content.split("---")[1:3][0]
                data = yaml.safe_load(front_matter)
                spdx_id = data.get("spdx-id")
                if spdx_id:
                    licenses[spdx_id] = {
                        "permissions": data.get("permissions", []),
                        "conditions": data.get("conditions", []),
                        "limitations": data.get("limitations", [])
                    }
    return licenses

def merge_licenses(spdx_data, choosealicense_data, uncategorized_only=False):
    """
    Merge SPDX and ChooseALicense metadata
    """
    merged = {}
    for license_id, spdx_info in spdx_data.items():
        choose_data = choosealicense_data.get(license_id)
        categorized = choose_data is not None
        if uncategorized_only and categorized:
            continue
        merged[license_id] = {
            "spdx": spdx_info,
            "categorized": categorized,
            "permissions": choose_data.get("permissions") if choose_data else [],
            "conditions": choose_data.get("conditions") if choose_data else [],
            "limitations": choose_data.get("limitations") if choose_data else [],
        }
    return merged

def main():
    parser = argparse.ArgumentParser(description="Merge SPDX and ChooseALicense metadata.")
    parser.add_argument("--update-submodules", action="store_true", help="Update git submodules.")
    parser.add_argument("--only-uncategorized", action="store_true", help="Include only uncategorized licenses.")
    args = parser.parse_args()

    if args.update_submodules:
        update_submodules()

    spdx_licenses = load_spdx_licenses(SPDX_JSON_DIR)
    choosealicense_metadata = load_choosealicense_metadata(CHOOSEALICENSE_DIR)
    merged = merge_licenses(spdx_licenses, choosealicense_metadata, uncategorized_only=args.only_uncategorized)

    for license_id, license_data in merged.items():
        safe_license_id = license_id.replace("/", "_")
        output_path = MERGED_DIR / f"{safe_license_id}.json"
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(license_data, f, indent=2, ensure_ascii=False)

if __name__ == "__main__":
    main()
