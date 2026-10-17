"""Test only the exceptions module without other dependencies."""

import sys
from pathlib import Path

# Add the package to Python path
sys.path.insert(0, str(Path(__file__).parent))


def test_exceptions_directly():
    """Test exceptions module directly."""
    print("Testing exceptions module...")
    
    try:
        # Import exceptions directly
        from mcp_client.exceptions import (
            MCPClientError,
            ConfigurationError,
            ValidationError,
            ToolExecutionError,
            TimeoutError,
            AuthenticationError,
            ServerError
        )
        
        # Test base exception
        base_error = MCPClientError("Base error", context={"key": "value"})
        assert str(base_error) == "Base error (context: key=value)"
        assert base_error.context["key"] == "value"
        
        # Test configuration error
        config_error = ConfigurationError(
            "Config error", 
            config_path="/test/path",
            field_name="test_field"
        )
        assert isinstance(config_error, MCPClientError)
        assert config_error.context["config_path"] == "/test/path"
        assert config_error.context["field_name"] == "test_field"
        
        # Test validation error
        validation_error = ValidationError(
            "Validation failed",
            field_path="servers.test.command",
            expected_type="string",
            actual_value=123
        )
        assert isinstance(validation_error, MCPClientError)
        assert validation_error.context["field_path"] == "servers.test.command"
        assert validation_error.context["expected_type"] == "string"
        assert validation_error.context["actual_value"] == 123
        
        # Test tool execution error
        tool_error = ToolExecutionError(
            "Tool failed",
            tool_name="calculator",
            server_name="math_server",
            arguments={"a": 1, "b": 2}
        )
        assert isinstance(tool_error, MCPClientError)
        assert tool_error.context["tool_name"] == "calculator"
        assert tool_error.context["server_name"] == "math_server"
        
        # Test timeout error
        timeout_error = TimeoutError(
            "Operation timed out",
            timeout_seconds=30.0,
            operation="connect"
        )
        assert isinstance(timeout_error, MCPClientError)
        assert timeout_error.context["timeout_seconds"] == 30.0
        assert timeout_error.context["operation"] == "connect"
        
        # Test authentication error
        auth_error = AuthenticationError(
            "Auth failed",
            auth_type="api_key"
        )
        assert isinstance(auth_error, MCPClientError)
        assert auth_error.context["auth_type"] == "api_key"
        
        # Test server error
        server_error = ServerError(
            "Server error",
            server_name="test_server",
            error_code="500"
        )
        assert isinstance(server_error, MCPClientError)
        assert server_error.context["server_name"] == "test_server"
        assert server_error.context["error_code"] == "500"
        
        print("✓ All exception classes work correctly")
        return True
        
    except Exception as e:
        print(f"❌ Exception test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_validation_utils():
    """Test validation utilities directly."""
    print("\nTesting validation utilities...")
    
    try:
        from mcp_client.utils.validation import (
            validate_non_empty_string,
            validate_positive_number,
            validate_url,
            validate_json_string
        )
        
        # Test non-empty string validation
        try:
            validate_non_empty_string("", "test_field")
            assert False, "Should have raised ValidationError"
        except Exception as e:
            assert "ValidationError" in str(type(e))
        
        validate_non_empty_string("valid string", "test_field")  # Should not raise
        
        # Test positive number validation
        try:
            validate_positive_number(-1, "test_field")
            assert False, "Should have raised ValidationError"
        except Exception as e:
            assert "ValidationError" in str(type(e))
        
        validate_positive_number(5.5, "test_field")  # Should not raise
        
        # Test URL validation
        try:
            validate_url("invalid-url", "url_field")
            assert False, "Should have raised ValidationError"
        except Exception as e:
            assert "ValidationError" in str(type(e))
        
        validate_url("https://example.com", "url_field")  # Should not raise
        
        # Test JSON validation
        try:
            validate_json_string("invalid json", "json_field")
            assert False, "Should have raised ValidationError"
        except Exception as e:
            assert "ValidationError" in str(type(e))
        
        result = validate_json_string('{"key": "value"}', "json_field")
        assert result["key"] == "value"
        
        print("✓ Validation utilities work correctly")
        return True
        
    except Exception as e:
        print(f"❌ Validation utils test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_retry_utils():
    """Test retry utilities directly."""
    print("\nTesting retry utilities...")
    
    try:
        from mcp_client.utils.retry import RetryPolicy, retry_with_backoff
        
        # Test retry policy
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
        assert delay2 > delay1  # Should increase with backoff
        
        # Test should_retry logic
        assert policy.should_retry(Exception("test"), 0) == True
        assert policy.should_retry(Exception("test"), 5) == False  # Exceeds max_retries
        
        print("✓ Retry utilities work correctly")
        return True
        
    except Exception as e:
        print(f"❌ Retry utils test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all independent tests."""
    print("🧪 Testing MCP Client components independently...\n")
    
    tests = [
        test_exceptions_directly,
        test_validation_utils,
        test_retry_utils,
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
        print("\n🎉 All independent component tests passed!")
        return True
    else:
        print(f"\n⚠️  Some tests failed.")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)