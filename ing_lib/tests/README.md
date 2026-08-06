# Test Suite for Ingenium Library

This directory contains comprehensive tests for the ingenium-lib project using pytest.

## Structure

- `conftest.py` - Pytest configuration and shared fixtures
- `test_*.py` - Individual test modules for each application
- `test_integration.py` - Integration tests that test multiple components together
- `README.md` - This file

## Test Coverage

### Applications Tested
- **ProjConfigBackup** - Tests for backup functionality including argument parsing, authentication, and data export
- **ProjConfigClear** - Tests for clearing project configurations with user confirmation
- **ProjConfigRestore** - Tests for restoring project configurations from backup files
- **ProjConfigCreateUpdateCS** - Tests for custom script creation/update including XML/JSON parsing
- **ProjConfigLoadDict** - Tests for loading dictionary files (AMPCS and XTCE formats)

### Core Modules Tested
- **common.py** - Tests for common utilities, authentication, and REST operations
- **project_config.py** - Tests for project configuration API functions

## Running Tests

### Run All Tests
```bash
cd ing-lib
python -m pytest tests/
```

### Run Specific Test File
```bash
python -m pytest tests/test_proj_config_backup.py
```

### Run with Verbose Output
```bash
python -m pytest -v tests/
```

### Run Tests with Coverage
```bash
python -m pytest --cov=. tests/
```

### Run Only Unit Tests
```bash
python -m pytest -m "unit" tests/
```

### Run Only Integration Tests
```bash
python -m pytest -m "integration" tests/
```

## Test Features

### Mocking Strategy
- External dependencies (HTTP requests, file system, authentication) are mocked
- Tests focus on application logic rather than external integrations
- Common fixtures provide consistent mock setups

### Fixtures
- `mock_server` - Provides test server URL
- `mock_authentication` - Mocks authentication to always succeed
- `sample_backup_data` - Provides sample backup data structure
- `temp_backup_file` - Creates temporary backup files for testing
- `temp_xml_file` - Creates temporary XML files for testing
- `mock_project_config_functions` - Mocks all project_config module functions

### Test Categories
- **Unit Tests**: Test individual functions and methods
- **Integration Tests**: Test component interactions and workflows
- **Error Handling**: Test error conditions and exception handling
- **Configuration**: Test SSL, authentication, and argument parsing

## Adding New Tests

When adding new tests:

1. Create test files following the naming convention `test_<module_name>.py`
2. Use the existing fixtures from `conftest.py` where applicable
3. Mock external dependencies appropriately
4. Include both positive and negative test cases
5. Test error handling and edge cases
6. Add markers for test categorization (`@pytest.mark.unit`, `@pytest.mark.integration`)

## Dependencies

The test suite requires:
- pytest (already in requirements.txt)
- unittest.mock (built into Python)
- tempfile (built into Python)

No additional test dependencies are required as we use Python's built-in testing capabilities. 