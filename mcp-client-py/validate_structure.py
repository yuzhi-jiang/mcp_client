"""Validate the MCP Client package structure."""

import json
from pathlib import Path


def validate_file_structure():
    """Validate that all expected files exist."""
    print("Validating file structure...")
    
    base_path = Path(__file__).parent
    
    expected_files = [
        # Main package files
        "mcp_client/__init__.py",
        "mcp_client/client.py", 
        "mcp_client/exceptions.py",
        "mcp_client/cli.py",
        "mcp_client/py.typed",
        
        # Configuration module
        "mcp_client/config/__init__.py",
        "mcp_client/config/models.py",
        "mcp_client/config/manager.py", 
        "mcp_client/config/validator.py",
        
        # Transport module
        "mcp_client/transport/__init__.py",
        "mcp_client/transport/base.py",
        "mcp_client/transport/stdio.py",
        "mcp_client/transport/sse.py",
        
        # Connection module
        "mcp_client/connection/__init__.py",
        "mcp_client/connection/manager.py",
        
        # Tools module
        "mcp_client/tools/__init__.py",
        "mcp_client/tools/manager.py",
        "mcp_client/tools/executor.py",
        
        # LLM module
        "mcp_client/llm/__init__.py",
        "mcp_client/llm/base.py",
        "mcp_client/llm/openai.py",
        "mcp_client/llm/conversation.py",
        
        # Utils module
        "mcp_client/utils/__init__.py",
        "mcp_client/utils/logging.py",
        "mcp_client/utils/retry.py",
        "mcp_client/utils/validation.py",
        
        # Project files
        "pyproject.toml",
        "README.md",
        "LICENSE",
        "CHANGELOG.md",
        "CONTRIBUTING.md",
        ".gitignore",
        
        # Examples
        "examples/basic_usage.py",
        "examples/config_examples/basic_config.json",
        "examples/config_examples/minimal_config.json",
    ]
    
    missing_files = []
    existing_files = []
    
    for file_path in expected_files:
        full_path = base_path / file_path
        if full_path.exists():
            existing_files.append(file_path)
        else:
            missing_files.append(file_path)
    
    print(f"✓ Found {len(existing_files)} expected files")
    
    if missing_files:
        print(f"❌ Missing {len(missing_files)} files:")
        for file_path in missing_files:
            print(f"  - {file_path}")
        return False
    
    print("✓ All expected files exist")
    return True


def validate_pyproject_toml():
    """Validate pyproject.toml structure."""
    print("\nValidating pyproject.toml...")
    
    pyproject_path = Path(__file__).parent / "pyproject.toml"
    
    if not pyproject_path.exists():
        print("❌ pyproject.toml not found")
        return False
    
    # Basic validation without TOML parser
    content = pyproject_path.read_text()
    
    required_sections = [
        "[build-system]",
        "[project]",
        "[tool.black]",
        "[tool.isort]",
        "[tool.mypy]",
        "[tool.pytest.ini_options]"
    ]
    
    missing_sections = []
    for section in required_sections:
        if section not in content:
            missing_sections.append(section)
    
    if missing_sections:
        print(f"❌ Missing sections in pyproject.toml: {missing_sections}")
        return False
    
    # Check for required project fields
    required_fields = [
        'name = "mcp-client"',
        'version = "0.1.0"',
        "dependencies = [",
        "mcp>=1.0.0",
        "openai>=1.0.0"
    ]
    
    missing_fields = []
    for field in required_fields:
        if field not in content:
            missing_fields.append(field)
    
    if missing_fields:
        print(f"❌ Missing fields in pyproject.toml: {missing_fields}")
        return False
    
    print("✓ pyproject.toml structure is valid")
    return True


def validate_package_exports():
    """Validate package __init__.py exports."""
    print("\nValidating package exports...")
    
    init_path = Path(__file__).parent / "mcp_client" / "__init__.py"
    
    if not init_path.exists():
        print("❌ mcp_client/__init__.py not found")
        return False
    
    content = init_path.read_text()
    
    # Check for key exports
    expected_exports = [
        "MCPClient",
        "Config",
        "ServerConfig",
        "MCPClientError",
        "ConfigurationError",
        "ValidationError"
    ]
    
    missing_exports = []
    for export in expected_exports:
        if f'"{export}"' not in content:
            missing_exports.append(export)
    
    if missing_exports:
        print(f"❌ Missing exports: {missing_exports}")
        return False
    
    print("✓ Package exports are correct")
    return True


def validate_examples():
    """Validate example files."""
    print("\nValidating examples...")
    
    examples_path = Path(__file__).parent / "examples"
    
    if not examples_path.exists():
        print("❌ Examples directory not found")
        return False
    
    # Check basic usage example
    basic_usage = examples_path / "basic_usage.py"
    if not basic_usage.exists():
        print("❌ basic_usage.py not found")
        return False
    
    content = basic_usage.read_text()
    if "from mcp_client import" not in content:
        print("❌ basic_usage.py doesn't import mcp_client")
        return False
    
    # Check config examples
    config_examples = examples_path / "config_examples"
    if not config_examples.exists():
        print("❌ config_examples directory not found")
        return False
    
    basic_config = config_examples / "basic_config.json"
    if basic_config.exists():
        try:
            config_data = json.loads(basic_config.read_text())
            if "servers" not in config_data:
                print("❌ basic_config.json missing 'servers' key")
                return False
        except json.JSONDecodeError:
            print("❌ basic_config.json is not valid JSON")
            return False
    
    print("✓ Examples are valid")
    return True


def validate_documentation():
    """Validate documentation files."""
    print("\nValidating documentation...")
    
    base_path = Path(__file__).parent
    
    # Check README
    readme_path = base_path / "README.md"
    if not readme_path.exists():
        print("❌ README.md not found")
        return False
    
    readme_content = readme_path.read_text(encoding='utf-8')
    if "# MCP Client" not in readme_content:
        print("❌ README.md missing main title")
        return False
    
    # Check CHANGELOG
    changelog_path = base_path / "CHANGELOG.md"
    if not changelog_path.exists():
        print("❌ CHANGELOG.md not found")
        return False
    
    # Check CONTRIBUTING
    contributing_path = base_path / "CONTRIBUTING.md"
    if not contributing_path.exists():
        print("❌ CONTRIBUTING.md not found")
        return False
    
    # Check LICENSE
    license_path = base_path / "LICENSE"
    if not license_path.exists():
        print("❌ LICENSE not found")
        return False
    
    print("✓ Documentation files are present")
    return True


def main():
    """Run all validation checks."""
    print("🔍 Validating MCP Client package structure...\n")
    
    validators = [
        validate_file_structure,
        validate_pyproject_toml,
        validate_package_exports,
        validate_examples,
        validate_documentation,
    ]
    
    results = []
    for validator in validators:
        try:
            result = validator()
            results.append(result)
        except Exception as e:
            print(f"❌ Validator {validator.__name__} failed: {e}")
            results.append(False)
    
    print(f"\n📊 Validation Results:")
    print(f"  ✓ Passed: {sum(results)}")
    print(f"  ❌ Failed: {len(results) - sum(results)}")
    print(f"  📈 Success Rate: {sum(results)/len(results)*100:.1f}%")
    
    if all(results):
        print("\n🎉 All validations passed! The MCP Client package is properly structured and ready for use.")
        return True
    else:
        print(f"\n⚠️  Some validations failed. Please review the issues above.")
        return False


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)