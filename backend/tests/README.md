# API Tests

This directory contains comprehensive tests for the Self-Evolving Taxonomy Agent API.

## Test Structure

- `conftest.py` - Pytest configuration and shared fixtures
- `test_auth.py` - Authentication endpoints tests
- `test_users.py` - User management endpoints tests
- `test_taxonomies.py` - Taxonomy CRUD operations tests
- `test_items.py` - Items management endpoints tests
- `test_nodes.py` - Taxonomy nodes endpoints tests
- `test_classification.py` - Classification and examination endpoints tests

## Setup

1. Install test dependencies:
```bash
cd backend
pip install -e ".[test]"
# or with uv:
uv pip install -e ".[test]"
```

2. Set up environment variables (create a `.env.test` file):
```env
MONGODB_URL=mongodb://localhost:27017
MONGODB_DB_NAME=test_taxonomy_agent
SECRET_KEY=test-secret-key
GOOGLE_CLIENT_ID=test-client-id
GOOGLE_CLIENT_SECRET=test-client-secret
```

## Running Tests

### Run all tests:
```bash
pytest
```

### Run tests with coverage:
```bash
pytest --cov=app --cov-report=html --cov-report=term-missing
```

### Run specific test file:
```bash
pytest tests/test_auth.py
```

### Run specific test class or method:
```bash
pytest tests/test_auth.py::TestAuthEndpoints::test_google_login
```

### Run tests by marker:
```bash
pytest -m unit        # Run unit tests only
pytest -m integration # Run integration tests only
pytest -m "not slow"  # Skip slow tests
```

### Run tests in parallel:
```bash
pytest -n auto  # Requires pytest-xdist
```

### Run tests with verbose output:
```bash
pytest -vv
```

## Test Coverage

After running tests with coverage, you can view the HTML report:
```bash
open htmlcov/index.html  # macOS
xdg-open htmlcov/index.html  # Linux
start htmlcov/index.html  # Windows
```

## Test Fixtures

Key fixtures available in `conftest.py`:

- `mock_db` - Mock MongoDB database
- `client` - Async HTTP test client
- `test_user` - Regular test user
- `superuser` - Superuser for admin tests
- `auth_headers` - Authentication headers with valid token
- `test_taxonomy` - Sample taxonomy
- `test_nodes` - Sample taxonomy nodes
- `test_items` - Sample items for classification
- `mock_google_oauth` - Mocked Google OAuth client
- `mock_classifier_service` - Mocked classification service

## Writing New Tests

1. Create test files with `test_` prefix
2. Use async functions for async endpoints
3. Use appropriate fixtures for setup
4. Follow the pattern:
   - Arrange: Set up test data
   - Act: Make the API call
   - Assert: Verify the response

Example:
```python
async def test_create_taxonomy(
    self, client: AsyncClient, auth_headers: dict, mock_db
):
    """Test creating a new taxonomy."""
    # Arrange
    taxonomy_data = {
        "name": "Test Taxonomy",
        "aspect": "category"
    }
    
    # Act
    response = await client.post(
        "/api/v1/taxonomies/",
        json=taxonomy_data,
        headers=auth_headers
    )
    
    # Assert
    assert response.status_code == 201
    data = response.json()
    assert data["taxonomy"]["name"] == "Test Taxonomy"
```

## Debugging Tests

### Run tests with print statements:
```bash
pytest -s
```

### Run tests with debugger:
```bash
pytest --pdb  # Drop into debugger on failure
pytest --pdbcls=IPython.terminal.debugger:TerminalPdb  # Use IPython debugger
```

### Run specific test with extra logging:
```bash
pytest tests/test_auth.py::test_google_login -vv --log-cli-level=DEBUG
```

## Common Issues

1. **Import errors**: Make sure you've installed test dependencies with `pip install -e ".[test]"`

2. **Database connection errors**: Tests use `mongomock-motor` to mock MongoDB, no real database needed

3. **Async warnings**: Use `pytest-asyncio` fixtures and mark async tests properly

4. **Token validation errors**: Check that test fixtures are creating valid tokens with correct secret key

## CI/CD Integration

Add to your CI pipeline:
```yaml
- name: Run tests
  run: |
    cd backend
    pip install -e ".[test]"
    pytest --cov=app --cov-report=xml --cov-report=term-missing

- name: Upload coverage
  uses: codecov/codecov-action@v3
  with:
    file: ./backend/coverage.xml
``` 