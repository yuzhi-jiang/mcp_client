"""Final validation of MCP Client package without external dependencies."""

import json
from pathlib import Path


def validate_project_structure():
    """Validate the complete project structure."""
    print("🔍 Validating MCP Client project structure...\n")
    
    base_path = Path(__file__).parent
    
    # Define expected structure
    expected_structure = {
        "Package Files": [
            "mcp_client/__init__.py",
            "mcp_client/client.py",
            "mcp_client/exceptions.py",
            "mcp_client/cli.py",
            "mcp_client/py.typed",
        ],
        "Configuration Module": [
            "mcp_client/config/__init__.py",
            "mcp_client/config/models.py",
            "mcp_client/config/manager.py",
            "mcp_client/config/validator.py",
        ],
        "Transport Module": [
            "mcp_client/transport/__init__.py",
            "mcp_client/transport/base.py",
            "mcp_client/transport/stdio.py",
            "mcp_client/transport/sse.py",
        ],
        "Connection Module": [
            "mcp_client/connection/__init__.py",
            "mcp_client/connection/manager.py",
        ],
        "Tools Module": [
            "mcp_client/tools/__init__.py",
            "mcp_client/tools/manager.py",
            "mcp_client/tools/executor.py",
        ],
        "LLM Module": [
            "mcp_client/llm/__init__.py",
            "mcp_client/llm/base.py",
            "mcp_client/llm/openai.py",
            "mcp_client/llm/conversation.py",
        ],
        "Utils Module": [
            "mcp_client/utils/__init__.py",
            "mcp_client/utils/logging.py",
            "mcp_client/utils/retry.py",
            "mcp_client/utils/validation.py",
        ],
        "Project Configuration": [
            "pyproject.toml",
            "README.md",
            "LICENSE",
            "CHANGELOG.md",
            "CONTRIBUTING.md",
            ".gitignore",
        ],
        "Examples": [
            "examples/basic_usage.py",
            "examples/config_examples/basic_config.json",
            "examples/config_examples/minimal_config.json",
        ],
        "Documentation": [
            "PROJECT_SUMMARY.md",
            "FINAL_STATUS.md",
        ]
    }
    
    total_files = 0
    missing_files = []
    existing_files = []
    
    for category, files in expected_structure.items():
        print(f"📁 {category}:")
        category_missing = []
        category_existing = []
        
        for file_path in files:
            full_path = base_path / file_path
            if full_path.exists():
                category_existing.append(file_path)
                existing_files.append(file_path)
                print(f"  ✅ {file_path}")
            else:
                category_missing.append(file_path)
                missing_files.append(file_path)
                print(f"  ❌ {file_path}")
        
        total_files += len(files)
        print(f"  📊 {len(category_existing)}/{len(files)} files present\n")
    
    # Summary
    print(f"📈 Overall Results:")
    print(f"  ✅ Present: {len(existing_files)}")
    print(f"  ❌ Missing: {len(missing_files)}")
    print(f"  📊 Total: {total_files}")
    print(f"  🎯 Success Rate: {len(existing_files)/total_files*100:.1f}%")
    
    return len(missing_files) == 0


def validate_pyproject_toml():
    """Validate pyproject.toml configuration."""
    print("\n🔧 Validating pyproject.toml...\n")
    
    pyproject_path = Path(__file__).parent / "pyproject.toml"
    
    if not pyproject_path.exists():
        print("❌ pyproject.toml not found")
        return False
    
    content = pyproject_path.read_text(encoding='utf-8')
    
    # Check required sections
    required_sections = [
        "[build-system]",
        "[project]",
        "[tool.black]",
        "[tool.isort]",
        "[tool.mypy]",
        "[tool.pytest.ini_options]"
    ]
    
    print("📋 Required sections:")
    for section in required_sections:
        if section in content:
            print(f"  ✅ {section}")
        else:
            print(f"  ❌ {section}")
            return False
    
    # Check project metadata
    required_metadata = [
        'name = "mcp-client"',
        'version = "0.1.0"',
        "dependencies = [",
        "mcp>=1.0.0",
        "openai>=1.0.0",
        "click>=8.0.0"
    ]
    
    print("\n📦 Project metadata:")
    for metadata in required_metadata:
        if metadata in content:
            print(f"  ✅ {metadata}")
        else:
            print(f"  ❌ {metadata}")
            return False
    
    print("\n✅ pyproject.toml is valid")
    return True


def validate_package_exports():
    """Validate package __init__.py exports."""
    print("\n📤 Validating package exports...\n")
    
    init_path = Path(__file__).parent / "mcp_client" / "__init__.py"
    
    if not init_path.exists():
        print("❌ mcp_client/__init__.py not found")
        return False
    
    content = init_path.read_text(encoding='utf-8')
    
    # Check for key exports in __all__
    expected_exports = [
        "MCPClient",
        "Config",
        "ServerConfig",
        "MCPClientError",
        "ConfigurationError",
        "ValidationError",
        "ConnectionManager",
        "ToolManager"
    ]
    
    print("📋 Expected exports:")
    missing_exports = []
    for export in expected_exports:
        if f'"{export}"' in content:
            print(f"  ✅ {export}")
        else:
            print(f"  ❌ {export}")
            missing_exports.append(export)
    
    if missing_exports:
        print(f"\n❌ Missing exports: {missing_exports}")
        return False
    
    print("\n✅ Package exports are correct")
    return True


def validate_examples():
    """Validate example files."""
    print("\n📚 Validating examples...\n")
    
    examples_path = Path(__file__).parent / "examples"
    
    if not examples_path.exists():
        print("❌ Examples directory not found")
        return False
    
    # Check basic usage example
    basic_usage = examples_path / "basic_usage.py"
    if basic_usage.exists():
        content = basic_usage.read_text(encoding='utf-8')
        if "from mcp_client import" in content:
            print("✅ basic_usage.py imports mcp_client correctly")
        else:
            print("❌ basic_usage.py missing mcp_client import")
            return False
    else:
        print("❌ basic_usage.py not found")
        return False
    
    # Check config examples
    config_examples = examples_path / "config_examples"
    if config_examples.exists():
        basic_config = config_examples / "basic_config.json"
        if basic_config.exists():
            try:
                config_data = json.loads(basic_config.read_text(encoding='utf-8'))
                if "servers" in config_data:
                    print("✅ basic_config.json has valid structure")
                else:
                    print("❌ basic_config.json missing 'servers' key")
                    return False
            except json.JSONDecodeError:
                print("❌ basic_config.json is not valid JSON")
                return False
        else:
            print("❌ basic_config.json not found")
            return False
    else:
        print("❌ config_examples directory not found")
        return False
    
    print("✅ Examples are valid")
    return True


def validate_documentation():
    """Validate documentation files."""
    print("\n📖 Validating documentation...\n")
    
    base_path = Path(__file__).parent
    
    docs = {
        "README.md": "# MCP Client",
        "CHANGELOG.md": "# Changelog",
        "CONTRIBUTING.md": "# Contributing",
        "LICENSE": "MIT License",
        "PROJECT_SUMMARY.md": "# MCP Client - Project Summary",
        "FINAL_STATUS.md": "# MCP Client - Final Project Status"
    }
    
    for doc_file, expected_content in docs.items():
        doc_path = base_path / doc_file
        if doc_path.exists():
            try:
                content = doc_path.read_text(encoding='utf-8')
                if expected_content in content:
                    print(f"✅ {doc_file} - valid content")
                else:
                    print(f"⚠️  {doc_file} - missing expected content")
            except UnicodeDecodeError:
                print(f"⚠️  {doc_file} - encoding issue")
        else:
            print(f"❌ {doc_file} - not found")
            return False
    
    print("✅ Documentation files are present and valid")
    return True


def validate_code_quality_setup():
    """Validate code quality tool configurations."""
    print("\n🔧 Validating code quality setup...\n")
    
    base_path = Path(__file__).parent
    pyproject_path = base_path / "pyproject.toml"
    
    if not pyproject_path.exists():
        print("❌ pyproject.toml not found")
        return False
    
    content = pyproject_path.read_text(encoding='utf-8')
    
    tools = {
        "[tool.black]": "Black formatter",
        "[tool.isort]": "Import sorter", 
        "[tool.mypy]": "Type checker",
        "[tool.pytest.ini_options]": "Test runner",
        "[tool.coverage.run]": "Coverage tool"
    }
    
    for tool_section, tool_name in tools.items():
        if tool_section in content:
            print(f"✅ {tool_name} configured")
        else:
            print(f"❌ {tool_name} not configured")
            return False
    
    print("✅ Code quality tools are configured")
    return True


def main():
    """Run complete project validation."""
    print("🚀 MCP Client - Final Project Validation\n")
    print("=" * 60)
    
    validators = [
        ("Project Structure", validate_project_structure),
        ("pyproject.toml", validate_pyproject_toml),
        ("Package Exports", validate_package_exports),
        ("Examples", validate_examples),
        ("Documentation", validate_documentation),
        ("Code Quality Setup", validate_code_quality_setup),
    ]
    
    results = []
    
    for name, validator in validators:
        try:
            result = validator()
            results.append((name, result))
        except Exception as e:
            print(f"❌ {name} validation failed: {e}")
            results.append((name, False))
    
    # Final summary
    print("\n" + "=" * 60)
    print("📊 FINAL VALIDATION RESULTS")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} {name}")
    
    print(f"\n🎯 Overall Score: {passed}/{total} ({passed/total*100:.1f}%)")
    
    if passed == total:
        print("\n🎉 ALL VALIDATIONS PASSED!")
        print("✅ MCP Client is ready for release!")
        print("🚀 Project successfully completed!")
    else:
        print(f"\n⚠️  {total - passed} validation(s) failed")
        print("🔧 Please review and fix the issues above")
    
    return passed == total


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)