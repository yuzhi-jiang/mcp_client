"""Test basic imports without external dependencies."""

import sys
from pathlib import Path

# Add the package to Python path
sys.path.insert(0, str(Path(__file__).parent))


def test_basic_imports():
    """Test imports that don't require external dependencies."""
    print("Testing basic imports...")
    
    try:
        # Test exception imports
        from mcp_client.exceptions import (
            MCPClientError,
            ConfigurationError,
            ValidationError,
            ToolExecutionError,
            TimeoutError,
            AuthenticationError
        )
        print("✓ Exception classes imported successfully")
        
        # Test utility imports
        from mcp_client.utils.validation import validate_non_empty_string
        from mcp_client.utils.retry import RetryPolicy
        print("✓ Utility classes imported successfully")
        
        # Test basic functionality
        try:
            validate_non_empty_string("", "test")
            assert False, "Should have raised ValidationError"
        except ValidationError:
            pass  # Expected
        
        validate_non_empty_string("valid", "test")  # Should not raise
        
        policy = RetryPolicy(max_retries=3)
        assert policy.max_retries == 3
        
        print("✓ Basic functionality works")
        
        return True
        
    except Exception as e:
        print(f"❌ Import test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_exception_hierarchy():
    """Test exception hierarchy."""
    print("\nTesting exception hierarchy...")
    
    try:
        from mcp_client.exceptions import (
            MCPClientError,
            ConfigurationError,
            ValidationError
        )
        
        # Test exception creation
        config_error = ConfigurationError("Test config error", config_path="/test")
        assert isinstance(config_error, MCPClientError)
        assert "config_path" in config_error.context
        
        validation_error = ValidationError("Test validation error", field_path="test.field")
        assert isinstance(validation_error, MCPClientError)
        assert "field_path" in validation_error.context
        
        print("✓ Exception hierarchy works correctly")
        return True
        
    except Exception as e:
        print(f"❌ Exception hierarchy test failed: {e}")
        return False


def main():
    """Run all import tests."""
    print("🧪 Testing MCP Client imports...\n")
    
    tests = [
        test_basic_imports,
        test_exception_hierarchy,
    ]
    
    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"❌ Test {test.__name__} failed: {e}")
            results.append(False)
    
    print(f"\n📊 Test Results:")
    print(f"  ✓ Passed: {sum(results)}")
    print(f"  ❌ Failed: {len(results) - sum(results)}")
    
    if all(results):
        print("\n🎉 All import tests passed! Basic functionality is working.")
        return True
    else:
        print(f"\n⚠️  Some tests failed.")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)