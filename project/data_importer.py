import sqlite3
import json
import os

DATABASE_PATH = 'licenses.db' # Assumes this file is in the root, relative to where app runs
RULES_FILE_PATH = 'data/rules.json'
LICENSES_DIR_PATH = 'data/licenses/'

def get_db_connection():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row # Optional: access columns by name
    conn.execute("PRAGMA foreign_keys = ON;") # Enforce foreign key constraints
    return conn

def import_rules():
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        with open(RULES_FILE_PATH, 'r') as f:
            rules_data = json.load(f)

        if not isinstance(rules_data, list):
            # This case might occur if rules.json is a dict of lists like {"permissions": [], ...}
            # For now, assuming rules_data is a flat list of rule objects as per docs/RULES.md
            # and how 'id', 'label', 'category' are referenced.
            print(f"Warning: {RULES_FILE_PATH} is not a flat list of rules. Adapting may be needed if import fails.")
            # Fallback or specific handling if structure is known to be different.
            # For now, proceed assuming it's a list, errors will indicate if not.

        imported_count = 0
        for rule in rules_data:
            try:
                # 'id' in rules.json maps to 'key' in the 'rules' table.
                cursor.execute(
                    "INSERT OR IGNORE INTO rules (key, label, description, category) VALUES (?, ?, ?, ?)",
                    (rule['id'], rule['label'], rule.get('description', ''), rule['category'])
                )
                if cursor.rowcount > 0:
                    imported_count += 1
            except sqlite3.IntegrityError as e:
                print(f"Error inserting rule {rule.get('id')}: {e}")
            except KeyError as e:
                print(f"Skipping rule due to missing key: {e}. Rule data: {rule}")

        conn.commit()
        print(f"Imported {imported_count} new rules from {RULES_FILE_PATH}.")

    except FileNotFoundError:
        print(f"Error: Rules file not found at {RULES_FILE_PATH}")
    except json.JSONDecodeError:
        print(f"Error: Could not decode JSON from {RULES_FILE_PATH}")
    except Exception as e:
        print(f"An unexpected error occurred during rule import: {e}")
    finally:
        if conn:
            conn.close()

def import_licenses():
    conn = get_db_connection()
    cursor = conn.cursor()

    imported_licenses_count = 0
    processed_files_count = 0

    try:
        if not os.path.exists(LICENSES_DIR_PATH):
            print(f"Error: Licenses directory not found at {LICENSES_DIR_PATH}")
            return

        for filename in os.listdir(LICENSES_DIR_PATH):
            if filename.endswith(".json") and not filename.lower().startswith("readme"):
                filepath = os.path.join(LICENSES_DIR_PATH, filename)
                processed_files_count += 1
                license_data = None # Initialize for error reporting
                try:
                    with open(filepath, 'r') as f:
                        license_data = json.load(f)

                    spdx_id = license_data.get('spdx_id')
                    if not spdx_id:
                        print(f"Warning: Missing 'spdx_id' in {filename}. Skipping.")
                        continue

                    license_title = license_data.get('title', license_data.get('name')) # 'title' from spec, 'name' common too
                    license_url = None
                    if isinstance(license_data.get('links'), list) and len(license_data['links']) > 0:
                         license_url = license_data['links'][0].get('url')
                    if not license_url:
                        license_url = license_data.get('url', license_data.get('text_url'))


                    cursor.execute(
                        "INSERT OR IGNORE INTO licenses (spdx_id, name, url, summary) VALUES (?, ?, ?, ?)",
                        (
                            spdx_id,
                            license_title,
                            license_url,
                            license_data.get('description', license_data.get('summary')) # 'description' from spec, 'summary' common
                        )
                    )
                    if cursor.rowcount > 0:
                        imported_licenses_count += 1

                    # Handle rules mapping
                    # The license files might list rule IDs under a 'rules' key (preferred)
                    # or under 'permissions', 'conditions', 'limitations' keys (like choosealicense)
                    current_license_rules = []
                    if 'rules' in license_data and isinstance(license_data['rules'], list):
                        current_license_rules = license_data['rules']
                    else: # Fallback to choosealicense style
                        for category_key in ['permissions', 'conditions', 'limitations']:
                            rule_keys_for_category = license_data.get(category_key, [])
                            if isinstance(rule_keys_for_category, list):
                                current_license_rules.extend(rule_keys_for_category)

                    for rule_key in current_license_rules:
                        try:
                            cursor.execute(
                                "INSERT OR IGNORE INTO license_rules_mapping (license_spdx_id, rule_key) VALUES (?, ?)",
                                (spdx_id, rule_key)
                            )
                        except sqlite3.IntegrityError as e:
                            print(f"Warning: Could not map rule '{rule_key}' to license '{spdx_id}': {e}. Ensure rule exists in 'rules' table and mapping is unique.")

                    conn.commit()

                except FileNotFoundError: # Should not happen if os.listdir worked
                    print(f"Error: License file {filepath} not found after listing.")
                except json.JSONDecodeError:
                    print(f"Error: Could not decode JSON from {filepath}")
                except KeyError as e:
                    print(f"Skipping license in {filename} due to missing key: {e}. License data read: {license_data}")
                except Exception as e:
                    print(f"An unexpected error occurred processing {filename}: {e}")

        print(f"Processed {processed_files_count} JSON files from {LICENSES_DIR_PATH}.")
        print(f"Imported {imported_licenses_count} new licenses (or updated existing).")

    except FileNotFoundError: # For the main LICENSES_DIR_PATH itself
        print(f"Error: Licenses directory not found at {LICENSES_DIR_PATH}")
    except Exception as e:
        print(f"An unexpected error occurred during license import: {e}")
    finally:
        if conn:
            conn.close()

def import_all_data():
    print("Starting data import...")
    # It's important to import rules first due to foreign key constraints
    print("Importing rules...")
    import_rules()
    print("\nImporting licenses and their rule mappings...")
    import_licenses()
    print("\nData import process finished.")

# For direct execution testing:
# if __name__ == '__main__':
#     print("Manual execution of data importer.")
#     print("Please ensure 'licenses.db' exists and schema is applied via Liquibase.")
#     # import_all_data()
