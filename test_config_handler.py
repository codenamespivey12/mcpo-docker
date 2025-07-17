#!/usr/bin/env python3
"""
Test script for the configuration handler.
"""

import os
import json
import tempfile
import sys
from config_handler import ConfigHandler, ConfigError, HAS_JSONSCHEMA


def test_valid_config():
    """Test loading a valid configuration."""
    handler = ConfigHandler('config.example.json')
    config = handler.load_config()
    assert 'mcpServers' in config
    assert handler.validate_config()
    print("✅ Valid configuration test passed")


def test_env_substitution():
    """Test environment variable substitution."""
    # Create a temporary config file with environment variables
    temp_config = {
        "mcpServers": {
            "test": {
                "command": "test",
                "args": ["--value=${TEST_VALUE}"],
                "env": {
                    "API_KEY": "${TEST_API_KEY}"
                }
            }
        }
    }
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(temp_config, f)
        temp_path = f.name
    
    try:
        # Set environment variables
        os.environ['TEST_VALUE'] = 'test-value'
        os.environ['TEST_API_KEY'] = 'test-api-key'
        
        # Load and process the config
        handler = ConfigHandler(temp_path)
        handler.load_config()
        processed = handler.get_config()
        
        # Check substitution
        assert processed['mcpServers']['test']['args'][0] == '--value=test-value'
        assert processed['mcpServers']['test']['env']['API_KEY'] == 'test-api-key'
        print("✅ Environment variable substitution test passed")
    finally:
        # Clean up
        os.unlink(temp_path)


def test_missing_env_var():
    """Test handling of missing environment variables."""
    # Create a temporary config file with environment variables
    temp_config = {
        "mcpServers": {
            "test": {
                "command": "test",
                "args": ["--value=${MISSING_VAR}"]
            }
        }
    }
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(temp_config, f)
        temp_path = f.name
    
    try:
        # Ensure the environment variable is not set
        if 'MISSING_VAR' in os.environ:
            del os.environ['MISSING_VAR']
        
        # Load and process the config
        handler = ConfigHandler(temp_path)
        handler.load_config()
        
        try:
            processed = handler.get_config()
            assert False, "Should have raised ConfigError"
        except ConfigError as e:
            assert "Missing required environment variables: MISSING_VAR" in str(e)
            print("✅ Missing environment variable test passed")
    finally:
        # Clean up
        os.unlink(temp_path)


def test_invalid_json():
    """Test handling of invalid JSON."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        f.write('{"invalid": json')
        temp_path = f.name
    
    try:
        handler = ConfigHandler(temp_path)
        try:
            handler.load_config()
            assert False, "Should have raised ConfigError"
        except ConfigError as e:
            assert "Invalid JSON" in str(e)
            print("✅ Invalid JSON test passed")
    finally:
        # Clean up
        os.unlink(temp_path)


def test_schema_validation():
    """Test schema validation."""
    # Create a config missing required fields
    temp_config = {
        "proxy": {
            "port": 8000
        }
    }
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(temp_config, f)
        temp_path = f.name
    
    try:
        handler = ConfigHandler(temp_path)
        handler.load_config()
        try:
            handler.validate_config()
            assert False, "Should have raised ConfigError"
        except ConfigError as e:
            # Check for either jsonschema validation error or our basic validation error
            error_msg = str(e)
            assert ("validation failed" in error_msg) or ("Missing required property" in error_msg)
            print("✅ Schema validation test passed")
    finally:
        # Clean up
        os.unlink(temp_path)


def test_merge_config():
    """Test merging configurations."""
    # Create base config
    base_config = {
        "mcpServers": {
            "test1": {
                "command": "test",
                "args": ["--arg1"],
                "env": {
                    "VAR1": "value1"
                }
            }
        },
        "proxy": {
            "port": 8000,
            "host": "0.0.0.0"
        }
    }
    
    # Create override config
    override_config = {
        "mcpServers": {
            "test1": {
                "args": ["--arg2"],
                "env": {
                    "VAR2": "value2"
                }
            },
            "test2": {
                "command": "test2",
                "args": ["--arg3"]
            }
        },
        "proxy": {
            "port": 9000
        }
    }
    
    # Create temporary files
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(base_config, f)
        base_path = f.name
        
    try:
        # Load base config
        handler = ConfigHandler(base_path)
        handler.load_config()
        
        # Merge with override config
        merged = handler.merge_config(override_config)
        
        # Check merged values
        assert merged["mcpServers"]["test1"]["command"] == "test"
        assert merged["mcpServers"]["test1"]["args"] == ["--arg2"]
        assert merged["mcpServers"]["test1"]["env"]["VAR1"] == "value1"
        assert merged["mcpServers"]["test1"]["env"]["VAR2"] == "value2"
        assert merged["mcpServers"]["test2"]["command"] == "test2"
        assert merged["proxy"]["port"] == 9000
        assert merged["proxy"]["host"] == "0.0.0.0"
        
        print("✅ Merge configuration test passed")
    finally:
        # Clean up
        os.unlink(base_path)


def test_write_config():
    """Test writing configuration to a file."""
    config = {
        "mcpServers": {
            "test": {
                "command": "test",
                "args": ["--arg"]
            }
        }
    }
    
    # Create a temporary file for the output
    with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as f:
        output_path = f.name
    
    try:
        # Create a temporary file for the input
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(config, f)
            input_path = f.name
        
        # Load and write the config
        handler = ConfigHandler(input_path)
        handler.load_config()
        handler.write_config(output_path)
        
        # Read the written config
        with open(output_path, 'r') as f:
            written_config = json.load(f)
        
        # Check that the written config matches the original
        assert written_config == config
        print("✅ Write configuration test passed")
    finally:
        # Clean up
        if os.path.exists(input_path):
            os.unlink(input_path)
        if os.path.exists(output_path):
            os.unlink(output_path)


def test_apply_defaults():
    """Test applying default values from the schema."""
    # Create a minimal config
    minimal_config = {
        "mcpServers": {
            "test": {
                "command": "test",
                "args": ["--arg"]
            }
        }
    }
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(minimal_config, f)
        config_path = f.name
    
    try:
        handler = ConfigHandler(config_path)
        handler.load_config()
        config_with_defaults = handler.apply_defaults()
        
        # Check that defaults were applied
        assert "proxy" in config_with_defaults
        assert "logging" in config_with_defaults
        assert "healthCheck" in config_with_defaults
        assert "resources" in config_with_defaults
        
        # Check specific default values
        assert config_with_defaults["proxy"]["port"] == 8000
        assert config_with_defaults["logging"]["level"] == "info"
        assert config_with_defaults["healthCheck"]["enabled"] is True
        assert config_with_defaults["resources"]["cpuLimit"] == 1
        
        print("✅ Apply defaults test passed")
    finally:
        # Clean up
        os.unlink(config_path)


def test_exa_mcp_config():
    """Test Exa MCP server configuration."""
    # Create a config with Exa MCP server
    exa_config = {
        "mcpServers": {
            "exa": {
                "command": "npx",
                "args": ["-y", "exa-mcp-server"],
                "env": {
                    "EXA_API_KEY": "${EXA_API_KEY}"
                },
                "disabled": False,
                "autoApprove": [
                    "web_search_exa",
                    "research_paper_search_exa",
                    "company_research_exa",
                    "crawling_exa",
                    "competitor_finder_exa",
                    "linkedin_search_exa",
                    "wikipedia_search_exa",
                    "github_search_exa"
                ]
            }
        }
    }
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(exa_config, f)
        config_path = f.name
    
    try:
        # Set environment variables
        os.environ['EXA_API_KEY'] = 'test-exa-api-key'
        
        # Load and process the config
        handler = ConfigHandler(config_path)
        handler.load_config()
        processed = handler.get_config()
        
        # Check configuration
        assert processed['mcpServers']['exa']['command'] == 'npx'
        assert processed['mcpServers']['exa']['args'] == ['-y', 'exa-mcp-server']
        assert processed['mcpServers']['exa']['env']['EXA_API_KEY'] == 'test-exa-api-key'
        assert processed['mcpServers']['exa']['autoApprove'] == [
            "web_search_exa",
            "research_paper_search_exa",
            "company_research_exa",
            "crawling_exa",
            "competitor_finder_exa",
            "linkedin_search_exa",
            "wikipedia_search_exa",
            "github_search_exa"
        ]
        print("✅ Exa MCP server configuration test passed")
    finally:
        # Clean up
        os.unlink(config_path)


if __name__ == "__main__":
    print("Running configuration handler tests...")
    test_valid_config()
    test_env_substitution()
    test_missing_env_var()
    test_invalid_json()
    test_schema_validation()
    test_merge_config()
    test_write_config()
    test_apply_defaults()
    test_exa_mcp_config()
    print("All tests passed! ✅")