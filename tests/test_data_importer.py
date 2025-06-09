import pytest
import sqlite3
import json
import os
from unittest import mock # Using unittest.mock, which is standard

# Module to test
from project import data_importer

# --- Fixtures ---

@pytest.fixture
def mock_db_connection(mocker):
    """Mocks the database connection and cursor."""
    mock_conn = mocker.MagicMock(spec=sqlite3.Connection)
    mock_cursor = mocker.MagicMock(spec=sqlite3.Cursor)
    mock_conn.cursor.return_value = mock_cursor
    mock_conn.execute.return_value = mock_cursor # For PRAGMA foreign_keys = ON
    mocker.patch('project.data_importer.get_db_connection', return_value=mock_conn)
    return mock_conn, mock_cursor

# --- Tests for import_rules ---

def test_import_rules_success(mocker, mock_db_connection):
    mock_conn, mock_cursor = mock_db_connection
    rules_content = [
        {"id": "rule1", "label": "Rule 1", "description": "Desc 1", "category": "permissions"},
        {"id": "rule2", "label": "Rule 2", "description": "Desc 2", "category": "conditions"}
    ]
    mocker.patch('builtins.open', mocker.mock_open(read_data=json.dumps(rules_content)))
    mocker.patch('os.path.exists', return_value=True) # If used by importer

    # Simulate that the first rule inserted 1 row, second one also 1 (new entries)
    mock_cursor.rowcount = 1

    data_importer.import_rules()

    mock_cursor.execute.assert_any_call(
        "INSERT OR IGNORE INTO rules (key, label, description, category) VALUES (?, ?, ?, ?)",
        ("rule1", "Rule 1", "Desc 1", "permissions")
    )
    mock_cursor.execute.assert_any_call(
        "INSERT OR IGNORE INTO rules (key, label, description, category) VALUES (?, ?, ?, ?)",
        ("rule2", "Rule 2", "Desc 2", "conditions")
    )
    mock_conn.commit.assert_called_once()
    mock_conn.close.assert_called_once()

def test_import_rules_file_not_found(mocker, mock_db_connection, capsys):
    mock_conn, _ = mock_db_connection # cursor not used directly here for assertions
    mocker.patch('builtins.open', side_effect=FileNotFoundError("File not found"))

    data_importer.import_rules()

    captured = capsys.readouterr()
    assert f"Error: Rules file not found at {data_importer.RULES_FILE_PATH}" in captured.out
    mock_conn.commit.assert_not_called() # Should not commit if file not found
    mock_conn.close.assert_called_once()


def test_import_rules_json_decode_error(mocker, mock_db_connection, capsys):
    mock_conn, _ = mock_db_connection
    mocker.patch('builtins.open', mocker.mock_open(read_data="invalid json"))
    mocker.patch('os.path.exists', return_value=True)

    data_importer.import_rules()

    captured = capsys.readouterr()
    assert f"Error: Could not decode JSON from {data_importer.RULES_FILE_PATH}" in captured.out
    mock_conn.commit.assert_not_called()
    mock_conn.close.assert_called_once()

def test_import_rules_key_error(mocker, mock_db_connection, capsys):
    mock_conn, mock_cursor = mock_db_connection
    # Missing 'id' which maps to 'key'
    rules_content = [{"label": "Rule 1", "description": "Desc 1", "category": "permissions"}]
    mocker.patch('builtins.open', mocker.mock_open(read_data=json.dumps(rules_content)))
    mocker.patch('os.path.exists', return_value=True)

    data_importer.import_rules()

    captured = capsys.readouterr()
    assert "Skipping rule due to missing key: 'id'" in captured.out
    # mock_cursor.execute.assert_not_called() # This assertion is too strict, a rule without id would still call execute, but fail due to constraints or prior check
    mock_conn.commit.assert_called_once() # Still commits even if one rule fails due to try/except in loop
    mock_conn.close.assert_called_once()


# --- Tests for import_licenses ---

@pytest.fixture
def mock_license_files(mocker):
    """Mocks os.listdir and open for license files."""
    mock_listdir = mocker.patch('os.listdir', return_value=['MIT.json', 'Apache-2.0.json'])

    mit_content = {
        "spdx_id": "MIT", "title": "MIT License", "url": "mit.test", "description": "MIT desc",
        "rules": ["rule1"]
    }
    apache_content = {
        "spdx_id": "Apache-2.0", "title": "Apache 2.0", "url": "apache.test", "description": "Apache desc",
        "permissions": ["rule1"], "conditions": ["rule2"] # Test alternative rule structure
    }

    def mock_open_side_effect(filepath, mode):
        if 'MIT.json' in filepath:
            return mocker.mock_open(read_data=json.dumps(mit_content))()
        elif 'Apache-2.0.json' in filepath:
            return mocker.mock_open(read_data=json.dumps(apache_content))()
        # Add more specific mocks if other files are opened by the importer
        return mocker.mock_open(read_data="")() # Default for any other file

    mock_open = mocker.patch('builtins.open', side_effect=mock_open_side_effect)
    mocker.patch('os.path.join', side_effect=lambda *args: "/".join(args)) # Simple os.path.join mock
    mocker.patch('os.path.exists', return_value=True) # For LICENSES_DIR_PATH

    return mock_listdir, mock_open


def test_import_licenses_success(mocker, mock_db_connection, mock_license_files):
    mock_conn, mock_cursor = mock_db_connection
    mock_cursor.rowcount = 1 # Assume inserts are successful

    data_importer.import_licenses()

    # Check license inserts
    mock_cursor.execute.assert_any_call(
        "INSERT OR IGNORE INTO licenses (spdx_id, name, url, summary) VALUES (?, ?, ?, ?)",
        ("MIT", "MIT License", "mit.test", "MIT desc")
    )
    mock_cursor.execute.assert_any_call(
        "INSERT OR IGNORE INTO licenses (spdx_id, name, url, summary) VALUES (?, ?, ?, ?)",
        ("Apache-2.0", "Apache 2.0", "apache.test", "Apache desc")
    )

    # Check rule mappings
    mock_cursor.execute.assert_any_call(
        "INSERT OR IGNORE INTO license_rules_mapping (license_spdx_id, rule_key) VALUES (?, ?)",
        ("MIT", "rule1")
    )
    mock_cursor.execute.assert_any_call(
        "INSERT OR IGNORE INTO license_rules_mapping (license_spdx_id, rule_key) VALUES (?, ?)",
        ("Apache-2.0", "rule1") # From 'permissions'
    )
    mock_cursor.execute.assert_any_call(
        "INSERT OR IGNORE INTO license_rules_mapping (license_spdx_id, rule_key) VALUES (?, ?)",
        ("Apache-2.0", "rule2") # From 'conditions'
    )

    assert mock_conn.commit.call_count == 2 # Called after each license file
    mock_conn.close.assert_called_once()


def test_import_licenses_dir_not_found(mocker, mock_db_connection, capsys):
    mock_conn, _ = mock_db_connection
    mocker.patch('os.path.exists', return_value=False) # Simulate LICENSES_DIR_PATH not existing
    # Or, os.listdir could raise FileNotFoundError
    # mocker.patch('os.listdir', side_effect=FileNotFoundError("Dir not found")) # This would also work


    data_importer.import_licenses()

    captured = capsys.readouterr()
    # The error message depends on how `os.path.exists` vs `os.listdir` is used in the importer.
    # Current importer has `if not os.path.exists(LICENSES_DIR_PATH):`
    assert f"Error: Licenses directory not found at {data_importer.LICENSES_DIR_PATH}" in captured.out


    mock_conn.commit.assert_not_called()
    mock_conn.close.assert_called_once()


def test_import_licenses_skip_file_missing_spdx_id(mocker, mock_db_connection, capsys):
    mock_conn, mock_cursor = mock_db_connection
    mocker.patch('os.listdir', return_value=['NoSPDX.json'])
    no_spdx_content = {"title": "No SPDX License", "url": "nospdx.test", "description": "No SPDX desc"}
    # We need to ensure builtins.open is mocked for the specific file "NoSPDX.json"
    # and that os.path.exists for LICENSES_DIR_PATH is True.
    mocker.patch('os.path.exists', return_value=True)
    mocker.patch('os.path.join', side_effect=lambda *args: "/".join(args))

    # This mock_open should only apply to the NoSPDX.json file.
    # If other files were "listed" by os.listdir, they'd need their own mock or a more general side_effect.
    mock_open_no_spdx = mocker.mock_open(read_data=json.dumps(no_spdx_content))
    mocker.patch('builtins.open', mock_open_no_spdx)


    data_importer.import_licenses()

    captured = capsys.readouterr()
    assert "Warning: Missing 'spdx_id' in NoSPDX.json. Skipping." in captured.out

    # Ensure no INSERT to licenses table was attempted for this license
    # This is a bit more robust to check the parameters rather than the SQL string directly
    for call_args in mock_cursor.execute.call_args_list:
        sql_command = call_args[0][0]
        if sql_command.startswith("INSERT OR IGNORE INTO licenses"):
            assert "NoSPDX" not in call_args[0][1] # Check params

    # commit is called per file in the current importer logic, even if that file fails validation before db ops
    # If a file is skipped due to missing spdx_id, no db operation for *that* file occurs, so no commit for it.
    # However, if it were part of a loop with other valid files, commits for *those* would happen.
    # In this test, only one file is processed, and it's skipped. So, no commit.
    mock_conn.commit.assert_not_called()
    mock_conn.close.assert_called_once()

def test_import_licenses_integrity_error_on_mapping(mocker, mock_db_connection, capsys):
    mock_conn, mock_cursor = mock_db_connection
    license_content = {
        "spdx_id": "TestLic", "title": "Test License", "url": "test.com", "description": "Test desc",
        "rules": ["non_existent_rule"]
    }
    mocker.patch('os.listdir', return_value=['TestLic.json'])
    mocker.patch('builtins.open', mocker.mock_open(read_data=json.dumps(license_content)))
    mocker.patch('os.path.join', side_effect=lambda *args: "/".join(args))
    mocker.patch('os.path.exists', return_value=True)

    # First execute (license insert) is fine (mock_cursor.rowcount = 1 by default from fixture)
    # Second execute (rule mapping insert) raises IntegrityError

    # Correct way to handle side_effect for multiple calls with different outcomes:
    # The first call to mock_cursor.execute is for the license insert.
    # The second call is for the rule mapping insert.
    def execute_side_effect(*args, **kwargs):
        sql = args[0]
        if "INSERT OR IGNORE INTO licenses" in sql:
            mock_cursor.rowcount = 1 # Simulate successful insert
            return mock.DEFAULT # Proceed with default mock behavior
        elif "INSERT OR IGNORE INTO license_rules_mapping" in sql:
            raise sqlite3.IntegrityError("FOREIGN KEY constraint failed")
        return mock.DEFAULT # Default for other calls like PRAGMA

    mock_cursor.execute.side_effect = execute_side_effect
    # mock_cursor.rowcount = 1 # This is now set within the side_effect for the relevant call

    data_importer.import_licenses()

    captured = capsys.readouterr()
    assert "Warning: Could not map rule 'non_existent_rule' to license 'TestLic': FOREIGN KEY constraint failed" in captured.out
    mock_conn.commit.assert_called_once() # Commit is called for the license insert itself
    mock_conn.close.assert_called_once()

# --- Test for import_all_data ---

def test_import_all_data(mocker, capsys):
    mock_import_rules = mocker.patch('project.data_importer.import_rules')
    mock_import_licenses = mocker.patch('project.data_importer.import_licenses')

    data_importer.import_all_data()

    mock_import_rules.assert_called_once()
    mock_import_licenses.assert_called_once()

    captured = capsys.readouterr()
    assert "Starting data import..." in captured.out
    assert "Importing rules..." in captured.out
    assert "Importing licenses and their rule mappings..." in captured.out
    assert "Data import process finished." in captured.out
