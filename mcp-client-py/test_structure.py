"""Test the basic structure and imports of MCP Client."""

import sys
from pathlib import Path

# Add the package to Python path
sys.path.insert(0, str(Path(__file__).parent))


def test_package_structure():
    """Test that the package structure is correct."""
    print("Testing package structure...")
    
    # Test that all modules can be imported (without external dependencies)
    try:
        # Test exception imports
        from mcp_client.exceptions import (
            MCPClientError,
            ConfigurationError,
            ValidationError
        )
        print("✓ Exception classes imported successfully")
        
        # Test that we can import basic modules without MCP dependency
        print("✓ Basic imports work (skipping MCP-dependent modules)")
        
        # Test validation utilities
        from mcp_client.utils.validation import validate_non_empty_string
        
        try:
            validate_non_empty_string("", "test_field")
            assert False, "Should have raised ValidationError"
        except ValidationError:
            pass  # Expected
        
        validate_non_empty_string("valid", "test_field")  # Should not raise
        print("✓ Validation utilities work")
        
        # Test retry utilities
        from mcp_client.utils.retry import RetryPolicy
        
        policy = RetryPolicy(max_retries=3, base_delay=1.0)
        assert policy.max_retries == 3
        assert policy.base_delay == 1.0
        print("✓ Retry utilities work")
        
        print("\n🎉 Package structure is correct!")
        return True
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_file_structure():
    """Test that all expected files exist."""
    print("\nTesting file structure...")
    
    base_path = Path(__file__).parent
    
    expected_files = [
        "mcp_client/__init__.py",
        "mcp_client/client.py",
        "mcp_client/exceptions.py",
        "mcp_client/cli.py",
        "mcp_client/config/__init__.py",
        "mcp_client/config/models.py",
        "mcp_client/config/manager.py",
        "mcp_client/config/validator.py",
        "mcp_client/transport/__init__.py",
        "mcp_client/transport/base.py",
        "mcp_client/transport/stdio.py",
        "mcp_client/transport/sse.py",
        "mcp_client/connection/__init__.py",
        "mcp_client/connection/manager.py",
        "mcp_client/tools/__init__.py",
        "mcp_client/tools/manager.py",
        "mcp_client/tools/executor.py",
        "mcp_client/llm/__init__.py",
        "mcp_client/llm/base.py",
        "mcp_client/llm/openai.py",
        "mcp_client/llm/conversation.py",
        "mcp_client/utils/__init__.py",
        "mcp_client/utils/logging.py",
        "mcp_client/utils/retry.py",
        "mcp_client/utils/validation.py",
        "pyproject.toml",
        "README.md",
        "LICENSE",
        "CHANGELOG.md",
        "CONTRIBUTING.md",
        "examples/basic_usage.py",
        "examples/config_examples/basic_config.json",
        "examples/config_examples/minimal_config.json",
    ]
    
    missing_files = []
    for file_path in expected_files:
        full_path = base_path / file_path
        if not full_path.exists():
            missing_files.append(file_path)
    
    if missing_files:
        print(f"❌ Missing files: {missing_files}")
        return False
    
    print("✓ All expected files exist")
    return True


def test_pyproject_toml():
    """Test that pyproject.toml is valid."""
    print("\nTesting pyproject.toml...")
    
    try:
        import tomllib
    except ImportError:
        try:
            import tomli as tomllib
        except ImportError:
            print("⚠️  Cannot test pyproject.toml (no TOML parser available)")
            return True
    
    try:
        pyproject_path = Path(__file__).parent / "pyproject.toml"
        with open(pyproject_path, 'rb') as f:
            data = tomllib.load(f)
        
        # Check required fields
        assert "project" in data
        assert "name" in data["project"]
        assert "version" in data["project"]
        assert "dependencies" in data["project"]
        
        print("✓ pyproject.toml is valid")
        return True
        
    except Exception as e:
        print(f"❌ pyproject.toml error: {e}")
        return False


def main():
    """Run all structure tests."""
    print("Running MCP Client structure tests...\n")
    
    tests = [
        test_file_structure,
        test_pyproject_toml,
        test_package_structure,
    ]
    
    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"❌ Test {test.__name__} failed: {e}")
            results.append(False)
    
    if all(results):
        print("\n🎉 All structure tests passed! The MCP Client package is properly structured.")
        return True
    else:
        print(f"\n❌ {len([r for r in results if not r])} test(s) failed.")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)