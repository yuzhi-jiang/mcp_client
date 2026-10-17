"""Test individual modules directly without package imports."""

import sys
from pathlib import Path

# Add the package to Python path
sys.path.insert(0, str(Path(__file__).parent))


def test_exceptions_module():
    """Test exceptions module directly."""
    print("Testing exceptions module...")
    
    try:
        # Import the exceptions module directly
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "exceptions", 
            Path(__file__).parent / "mcp_client" / "exceptions.py"
        )
        exceptions_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(exceptions_module)
        
        # Test exception classes
        MCPClientError = exceptions_module.MCPClientError
        ConfigurationError = exceptions_module.ConfigurationError
        ValidationError = exceptions_module.ValidationError
        
        # Test base exception
        base_error = MCPClientError("Base error", context={"key": "value"})
        assert "Base error" in str(base_error)
        assert base_error.context["key"] == "value"
        
        # Test configuration error
        config_error = ConfigurationError(
            "Config error", 
            config_path="/test/path",
            field_name="test_field"
        )
        assert isinstance(config_error, MCPClientError)
        assert config_error.context["config_path"] == "/test/path"
        
        # Test validation error
        validation_error = ValidationError(
            "Validation failed",
            field_path="servers.test.command",
            expected_type="string",
            actual_value=123
        )
        assert isinstance(validation_error, MCPClientError)
        assert validation_error.context["field_path"] == "servers.test.command"
        
        print("✓ Exception classes work correctly")
        return True
        
    except Exception as e:
        print(f"❌ Exception test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_validation_module():
    """Test validation module directly."""
    print("\nTesting validation module...")
    
    try:
        # Import validation module directly
        import importlib.util
        
        # First import exceptions for ValidationError
        exceptions_spec = importlib.util.spec_from_file_location(
            "exceptions", 
            Path(__file__).parent / "mcp_client" / "exceptions.py"
        )
        exceptions_module = importlib.util.module_from_spec(exceptions_spec)
        exceptions_spec.loader.exec_module(exceptions_module)
        
        # Add to sys.modules so validation can import it
        sys.modules['mcp_client.exceptions'] = exceptions_module
        
        # Now import validation module
        validation_spec = importlib.util.spec_from_file_location(
            "validation", 
            Path(__file__).parent / "mcp_client" / "utils" / "validation.py"
        )
        validation_module = importlib.util.module_from_spec(validation_spec)
        validation_spec.loader.exec_module(validation_module)
        
        # Test validation functions
        validate_non_empty_string = validation_module.validate_non_empty_string
        validate_positive_number = validation_module.validate_positive_number
        validate_url = validation_module.validate_url
        
        # Test non-empty string validation
        try:
            validate_non_empty_string("", "test_field")
            assert False, "Should have raised ValidationError"
        except exceptions_module.ValidationError:
            pass  # Expected
        
        validate_non_empty_string("valid string", "test_field")  # Should not raise
        
        # Test positive number validation
        try:
            validate_positive_number(-1, "test_field")
            assert False, "Should have raised ValidationError"
        except exceptions_module.ValidationError:
            pass  # Expected
        
        validate_positive_number(5.5, "test_field")  # Should not raise
        
        # Test URL validation
        try:
            validate_url("invalid-url", "url_field")
            assert False, "Should have raised ValidationError"
        except exceptions_module.ValidationError:
            pass  # Expected
        
        validate_url("https://example.com", "url_field")  # Should not raise
        
        print("✓ Validation functions work correctly")
        return True
        
    except Exception as e:
        print(f"❌ Validation test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_retry_module():
    """Test retry module directly."""
    print("\nTesting retry module...")
    
    try:
        # Import retry module directly
        import importlib.util
        
        # First import exceptions
        exceptions_spec = importlib.util.spec_from_file_location(
            "exceptions", 
            Path(__file__).parent / "mcp_client" / "exceptions.py"
        )
        exceptions_module = importlib.util.module_from_spec(exceptions_spec)
        exceptions_spec.loader.exec_module(exceptions_module)
        sys.modules['mcp_client.exceptions'] = exceptions_module
        
        # Import retry module
        retry_spec = importlib.util.spec_from_file_location(
            "retry", 
            Path(__file__).parent / "mcp_client" / "utils" / "retry.py"
        )
        retry_module = importlib.util.module_from_spec(retry_spec)
        retry_spec.loader.exec_module(retry_module)
        
        # Test retry policy
        RetryPolicy = retry_module.RetryPolicy
        
        policy = RetryPolicy(
            max_retries=3,
            base_delay=1.0,
            max_delay=10.0,
            backoff_factor=2.0
        )
        
        assert policy.max_retries == 3
        assert policy.base_delay == 1.0
        assert policy.max_delay == 10.0
        assert policy.backoff_factor == 2.0
        
        # Test delay calculation
        delay1 = policy.calculate_delay(0)  # First retry
        delay2 = policy.calculate_delay(1)  # Second retry
        assert delay2 >= delay1  # Should increase with backoff (accounting for jitter)
        
        # Test should_retry logic
        assert policy.should_retry(Exception("test"), 0) == True
        assert policy.should_retry(Exception("test"), 5) == False  # Exceeds max_retries
        
        print("✓ Retry utilities work correctly")
        return True
        
    except Exception as e:
        print(f"❌ Retry test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_file_structure():
    """Test that key files exist and have expected content."""
    print("\nTesting file structure...")
    
    try:
        base_path = Path(__file__).parent
        
        # Test key files exist
        key_files = [
            "mcp_client/exceptions.py",
            "mcp_client/utils/validation.py", 
            "mcp_client/utils/retry.py",
            "mcp_client/utils/logging.py",
            "pyproject.toml",
            "README.md",
            "LICENSE"
        ]
        
        for file_path in key_files:
            full_path = base_path / file_path
            if not full_path.exists():
                print(f"❌ Missing file: {file_path}")
                return False
        
        # Test pyproject.toml has required content
        pyproject_content = (base_path / "pyproject.toml").read_text()
        required_content = [
            'name = "mcp-client"',
            'version = "0.1.0"',
            "[build-system]",
            "[project]"
        ]
        
        for content in required_content:
            if content not in pyproject_content:
                print(f"❌ Missing content in pyproject.toml: {content}")
                return False
        
        # Test README has basic content
        readme_content = (base_path / "README.md").read_text(encoding='utf-8')
        if "# MCP Client" not in readme_content:
            print("❌ README missing main title")
            return False
        
        print("✓ File structure is correct")
        return True
        
    except Exception as e:
        print(f"❌ File structure test failed: {e}")
        return False


def main():
    """Run all individual module tests."""
    print("🧪 Testing MCP Client individual modules...\n")
    
    tests = [
        test_file_structure,
        test_exceptions_module,
        test_validation_module,
        test_retry_module,
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
    print(f"  📈 Success Rate: {sum(results)/len(results)*100:.1f}%")
    
    if all(results):
        print("\n🎉 All individual module tests passed!")
        print("The core functionality is working correctly.")
        return True
    else:
        print(f"\n⚠️  Some tests failed.")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)