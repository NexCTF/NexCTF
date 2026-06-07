from fastapi_toolsets.fixtures import FixtureRegistry

from nexctf.fixtures import development, production, testing

fixture_registry = FixtureRegistry()
fixture_registry.include_registry(registry=development.fixtures)
fixture_registry.include_registry(registry=production.fixtures)

test_fixture_registry = FixtureRegistry()
test_fixture_registry.include_registry(registry=testing.fixtures)
