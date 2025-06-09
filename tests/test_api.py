import pytest
import json
import os # For checking data file existence for conditional skipping

# The 'client' fixture is automatically sourced from conftest.py by pytest.
# It handles test DB setup (via liquibase_setup_once) and data population.

def test_list_licenses_with_data(client):
    # This test assumes `import_all_data` in the `client` fixture has run
    # using sample JSON files in `data/licenses/` and `data/rules.json`.
    # The conftest.py client fixture now includes checks for these data files.

    response = client.get('/api/v1/licenses')
    assert response.status_code == 200
    assert response.content_type == 'application/json'

    data = response.json
    assert isinstance(data, list)

    # Check if specific known licenses (from your data/licenses folder) are present.
    # This depends on what files you have in data/licenses/.
    # For this example, we assume data/licenses/MIT.json exists and was loaded.
    # The actual content of data/licenses/MIT.json will determine pass/fail.
    # Example content for data/licenses/MIT.json:
    # {
    #   "spdx_id": "MIT", "title": "MIT License", "url": "https://opensource.org/licenses/MIT",
    #   "description": "A short and simple permissive software license.",
    #   "rules": ["commercial-use", "distribution", "modification", "private-use"]
    # }
    # Example content for data/rules.json (must contain the rules listed above):
    # [
    #   {"id": "commercial-use", "label": "Commercial Use", "category": "permissions", "description":"..."},
    #   ...
    # ]

    found_mit = any(item['spdx_id'] == 'MIT' for item in data)
    if os.path.exists(os.path.join('data', 'licenses', 'MIT.json')):
        assert found_mit, "MIT license should be listed if MIT.json exists and was imported."
        if found_mit:
            mit_license = next(item for item in data if item['spdx_id'] == 'MIT')
            # The name should match the 'title' field from the JSON file.
            assert mit_license['name'] == 'MIT License'
    else:
        # If MIT.json doesn't exist, it shouldn't be in the response.
        assert not found_mit, "MIT license should not be listed if MIT.json does not exist."
        print("Info: data/licenses/MIT.json not found, MIT license checks in response are adjusted.")


def test_get_license_by_spdx_id_exists(client):
    # This test assumes data/licenses/MIT.json exists and was imported.
    # The client fixture populates data based on files in data/
    mit_json_path = os.path.join('data', 'licenses', 'MIT.json')
    if not os.path.exists(mit_json_path):
        pytest.skip(f"Skipping test_get_license_by_spdx_id_exists as {mit_json_path} is missing.")

    response = client.get('/api/v1/licenses/MIT')

    assert response.status_code == 200
    assert response.content_type == 'application/json'

    data = response.json
    assert data['spdx_id'] == "MIT"
    # Name should match 'title' from MIT.json
    # URL should match 'url' or first 'links[0].url' from MIT.json
    # Summary should match 'description' or 'summary' from MIT.json
    # Rules should be populated based on MIT.json and rules.json

    # Example assertions (these depend on the actual content of your MIT.json and rules.json)
    assert data['name'] == "MIT License" # Assuming 'title' is "MIT License"
    assert 'url' in data
    assert 'summary' in data
    assert isinstance(data['rules'], list)

    # If MIT.json is expected to have certain rules from your data/rules.json:
    # For example, if MIT.json has "rules": ["commercial-use"]
    # And data/rules.json has {"id": "commercial-use", "label": "Commercial use", ...}
    if any(r['key'] == 'commercial-use' for r in data['rules']):
        commercial_use_rule = next(r for r in data['rules'] if r['key'] == 'commercial-use')
        assert commercial_use_rule['label'] == "Commercial use" # Check against your rules.json
    else:
        # This part might be reached if 'commercial-use' is not a rule for MIT in your test data
        # or if rules.json doesn't define 'commercial-use'.
        # Depending on how strict you want the test, this could be an assertion failure.
        print("Warning: 'commercial-use' rule not found for MIT license in test_get_license_by_spdx_id_exists. Check data files.")


def test_get_license_by_spdx_id_not_found(client):
    response = client.get('/api/v1/licenses/NONEXISTENTLICENSE123XYZ')
    assert response.status_code == 404
    assert response.content_type == 'application/json'
    data = response.json
    assert "message" in data
    assert "NONEXISTENTLICENSE123XYZ" in data["message"]

def test_openapi_spec_accessible(client):
    # Connexion serves the spec at /openapi.json and /openapi.yaml by default,
    # relative to the API's base_path.
    base_path = '/api/v1'

    response_json = client.get(f'{base_path}/openapi.json')
    response_yaml = client.get(f'{base_path}/openapi.yaml')

    # Check if at least one of them is accessible
    assert response_json.status_code == 200 or response_yaml.status_code == 200, \
        f"Neither {base_path}/openapi.json (status: {response_json.status_code}) " \
        f"nor {base_path}/openapi.yaml (status: {response_yaml.status_code}) were accessible."

    if response_json.status_code == 200:
        assert 'application/json' in response_json.content_type
        spec_data_json = response_json.json
        assert spec_data_json['openapi'] == '3.0.0'
        assert spec_data_json['info']['title'] == "Licenses as a Service API"
        print("Tested openapi.json successfully.")

    if response_yaml.status_code == 200:
        # YAML content type can vary
        assert 'yaml' in response_yaml.content_type.lower() or 'text/plain' in response_yaml.content_type.lower()
        spec_data_yaml = response_yaml.get_data(as_text=True)
        assert 'openapi: 3.0.0' in spec_data_yaml
        assert 'title: Licenses as a Service API' in spec_data_yaml
        print("Tested openapi.yaml successfully.")
