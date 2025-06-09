import sqlite3
# Assuming get_db_connection is in data_importer.py or a shared db_utils.py
# For now, let's put a simplified version here or import from data_importer
# To avoid circular dependencies if data_importer imports app, better to have a separate db util
# For this step, let's keep it simple and redefine a local get_db_connection
# In a refactor, this would go into a project.db module.

DATABASE_PATH = 'licenses.db' # Relative to project root

def get_db_connection():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row # Access columns by name
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def listLicenses():
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT spdx_id, name FROM licenses ORDER BY name ASC")
        licenses = cursor.fetchall() # Fetches all rows as a list of Row objects

        # Convert Row objects to dictionaries matching the LicenseSummary schema
        result = [{"spdx_id": lic['spdx_id'], "name": lic['name']} for lic in licenses]
        return result, 200
    except sqlite3.Error as e:
        print(f"Database error in listLicenses: {e}")
        return {"error": "Failed to retrieve licenses", "details": str(e)}, 500
    finally:
        if conn:
            conn.close()

def getLicenseBySpdxId(spdx_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Fetch license details
        cursor.execute("SELECT spdx_id, name, url, summary FROM licenses WHERE spdx_id = ?", (spdx_id,))
        license_row = cursor.fetchone()

        if not license_row:
            return {"message": f"License with SPDX ID '{spdx_id}' not found."}, 404

        license_details = dict(license_row) # Convert Row to dict

        # Fetch associated rules
        cursor.execute('''
            SELECT r.key, r.label, r.description, r.category
            FROM rules r
            JOIN license_rules_mapping lrm ON r.key = lrm.rule_key
            WHERE lrm.license_spdx_id = ?
        ''', (spdx_id,))
        rules_rows = cursor.fetchall()

        license_details['rules'] = [dict(rule_row) for rule_row in rules_rows]

        return license_details, 200

    except sqlite3.Error as e:
        print(f"Database error in getLicenseBySpdxId for {spdx_id}: {e}")
        return {"error": f"Failed to retrieve license {spdx_id}", "details": str(e)}, 500
    finally:
        if conn:
            conn.close()

# Note: If using Connexion's default Flask server for development,
# ensure it can find the 'licenses.db' file correctly.
# If 'licenses.db' is in the root, and app.py is in 'project/',
# the relative path '../licenses.db' might be needed if DATABASE_PATH
# is resolved from api_handlers.py's location.
# However, DATABASE_PATH = 'licenses.db' assumes the script/app is run from the project root.
# This is consistent with how `flask run` typically works.
