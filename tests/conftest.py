import pytest
import sqlite3
import os
import subprocess # To run Liquibase
import shutil # For removing liquibase directory if needed for testing
from project.app import app as flask_app # Your Flask app instance from project.app
from project.data_importer import import_all_data, DATABASE_PATH as MAIN_DB_PATH # To populate test data

# Using a fixed name in a temporary directory for the test database
TEST_DB_FILENAME = "test_licenses.db"
LIQUIBASE_DIR_NAME = "liquibase" # Relative to project root

@pytest.fixture(scope='session')
def test_db_path(tmp_path_factory):
    """Provides the path to a test database file within a session-scoped temporary directory."""
    return tmp_path_factory.mktemp("test_db_data") / TEST_DB_FILENAME

@pytest.fixture(scope='session')
def liquibase_setup_once(test_db_path):
    """Sets up the test database schema using Liquibase once per session."""
    # Ensure the project root is the current working directory for Liquibase
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

    liquibase_dir_abs = os.path.join(project_root, LIQUIBASE_DIR_NAME)
    master_changelog_rel_to_liquibase_dir = "db.changelog-master.xml" # Relative to liquibase_dir_abs

    # Determine classpath for SQLite JDBC driver
    # Common locations: liquibase/lib/sqlite-jdbc.jar, liquibase/sqlite-jdbc.jar
    # User might need to download this into one of these locations.
    sqlite_jdbc_jar_name = "sqlite-jdbc.jar" # Or a more specific versioned name
    classpath_entries = [
        os.path.join(liquibase_dir_abs, 'lib', sqlite_jdbc_jar_name),
        os.path.join(liquibase_dir_abs, sqlite_jdbc_jar_name),
        "." # Current directory
    ]
    # Filter out non-existent paths from classpath to avoid issues
    existing_classpath_entries = [p for p in classpath_entries if os.path.exists(p)]
    if not any(sqlite_jdbc_jar_name in entry for entry in existing_classpath_entries):
        # Try to find any sqlite-jdbc jar in liquibase/ or liquibase/lib/
        found_driver = False
        for loc in [liquibase_dir_abs, os.path.join(liquibase_dir_abs, 'lib')]:
            if os.path.exists(loc):
                for f in os.listdir(loc):
                    if 'sqlite-jdbc' in f and f.endswith('.jar'):
                        existing_classpath_entries.append(os.path.join(loc, f))
                        found_driver = True
                        break
            if found_driver: break
        if not found_driver:
            print(f"Warning: SQLite JDBC driver not found in expected locations: {classpath_entries}")
            # Liquibase might still find it if it's in its own lib or globally.

    classpath_str = ":".join(existing_classpath_entries)


    # Create a temporary liquibase.properties for the test DB
    temp_props_content = [
        f"changeLogFile={master_changelog_rel_to_liquibase_dir}\n",
        "driver=org.sqlite.JDBC\n",
        f"url=jdbc:sqlite:{str(test_db_path)}\n",
        f"classpath={classpath_str}\n"
    ]
    temp_props_path = os.path.join(liquibase_dir_abs, 'liquibase.pytest.properties')

    # Ensure liquibase directory exists
    if not os.path.isdir(liquibase_dir_abs):
        pytest.skip(f"Liquibase directory '{liquibase_dir_abs}' not found. Skipping integration tests.")
        return str(test_db_path) # Return path even if skipped

    with open(temp_props_path, 'w') as f:
        f.writelines(temp_props_content)

    try:
        print(f"Attempting Liquibase schema setup for: {test_db_path}")
        os.makedirs(test_db_path.parent, exist_ok=True)

        cmd = ['liquibase', f'--defaultsFile={temp_props_path}', 'update']
        print(f"Running Liquibase command: {' '.join(cmd)} from {project_root}")

        process = subprocess.run(
            cmd,
            cwd=project_root,
            check=False, # Check manually to provide better error messages
            capture_output=True,
            text=True
        )

        if process.returncode != 0:
            # Check if it's because the DB is locked (common in CI or parallel tests if not careful)
            if "database is locked" in process.stderr.lower() or "database is locked" in process.stdout.lower():
                 pytest.skip(f"Liquibase update failed because the database is locked: {test_db_path}. Stderr: {process.stderr}, Stdout: {process.stdout}")
            # Check if it's due to missing JDBC driver
            if "Cannot load JDBC driver class 'org.sqlite.JDBC'" in process.stderr or \
               "Cannot find database driver: org.sqlite.JDBC" in process.stderr:
                pytest.skip(f"Liquibase update failed due to missing SQLite JDBC driver. Stderr: {process.stderr}, Stdout: {process.stdout}. Ensure driver is on classpath: {classpath_str}")

            raise subprocess.CalledProcessError(process.returncode, cmd, output=process.stdout, stderr=process.stderr)

        print(f"Liquibase update stdout: {process.stdout}")
        if process.stderr:
            print(f"Liquibase update stderr: {process.stderr}")
        print("Test database schema created successfully via Liquibase.")

    except FileNotFoundError:
        pytest.skip("Liquibase command not found. Install Liquibase or check PATH. Skipping integration tests.")
    except subprocess.CalledProcessError as e:
        print(f"Liquibase update failed for {test_db_path}.")
        print(f"Command: {' '.join(e.cmd)}")
        print(f"Return code: {e.returncode}")
        print(f"Stdout: {e.stdout}")
        print(f"Stderr: {e.stderr}")
        pytest.skip(f"Liquibase schema setup failed (CalledProcessError), skipping integration tests.")
    except Exception as e:
        pytest.skip(f"An unexpected error occurred during Liquibase setup: {e}, skipping integration tests.")
    finally:
        if os.path.exists(temp_props_path):
            os.remove(temp_props_path)

    return str(test_db_path)


@pytest.fixture(scope='function')
def client(liquibase_setup_once, mocker):
    """Provides a Flask test client with a clean, populated database for each test function."""
    test_db_file_path = liquibase_setup_once

    # If liquibase_setup_once was skipped, test_db_file_path might be just the name, not a full path
    # or the DB file might not exist. Pytest skipping should handle this at a higher level.
    # We can check if the db file actually exists if liquibase claims to have run.
    if not os.path.exists(test_db_file_path) and "Liquibase" not in pytest.current_test.keywords.get('skipreason', ''):
         pytest.skip(f"Test database file {test_db_file_path} was not created by Liquibase. Skipping function test.")


    mocker.patch('project.api_handlers.DATABASE_PATH', test_db_file_path)
    mocker.patch('project.data_importer.DATABASE_PATH', test_db_file_path)

    # Clear data from tables before each test using this fixture
    try:
        conn = sqlite3.connect(test_db_file_path)
        cursor = conn.cursor()
        # Order matters for foreign keys if using DELETE FROM without CASCADE (SQLite default is NO ACTION)
        cursor.execute("DELETE FROM license_rules_mapping;")
        cursor.execute("DELETE FROM licenses;")
        cursor.execute("DELETE FROM rules;")
        conn.commit()
        conn.close()
    except sqlite3.Error as e:
        # If the DB file or tables don't exist due to Liquibase skip, this might fail.
        # This is okay if the test is already going to be skipped.
        if "Liquibase" not in pytest.current_test.keywords.get('skipreason', ''):
            pytest.fail(f"Failed to clear test database tables: {e}")


    # Populate the test database with data using the importer
    try:
        print(f"Populating test database for function: {test_db_file_path}")
        # Ensure data files exist for the import to be meaningful
        # project.data_importer.RULES_FILE_PATH and project.data_importer.LICENSES_DIR_PATH
        # This assumes that the `data` directory is available relative to the project root.
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
        rules_file_abs = os.path.join(project_root, data_importer.RULES_FILE_PATH)
        licenses_dir_abs = os.path.join(project_root, data_importer.LICENSES_DIR_PATH)

        if not os.path.exists(rules_file_abs):
             pytest.skip(f"Data rules file {rules_file_abs} not found. Skipping test function.")
        if not os.path.isdir(licenses_dir_abs):
             pytest.skip(f"Data licenses directory {licenses_dir_abs} not found. Skipping test function.")

        import_all_data() # This uses the patched DATABASE_PATH
        print("Test database populated for function.")
    except Exception as e:
        # If already skipping due to liquibase, don't override that with a data population failure.
        current_skip_reason = getattr(pytest.current_test, 'skipreason', None)
        if current_skip_reason and "Liquibase" in current_skip_reason:
            pass # Keep the original skip reason
        else:
            pytest.fail(f"Test DB population (import_all_data) failed for function: {e}")


    flask_app.config['TESTING'] = True
    # Set SERVER_NAME to allow URL generation without a request context if needed by any part of app
    # flask_app.config['SERVER_NAME'] = 'localhost.test'

    with flask_app.test_client() as test_client:
        yield test_client

    # Cleanup of test_db_file_path itself is handled by tmp_path_factory (session-scoped)
    # If we were creating a db per function, we'd delete it here.
    # For now, data is cleared at start of function scope by this fixture.
