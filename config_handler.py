#!/usr/bin/env python3
"""
Configuration handler for MCP Docker setup.
Handles loading, validating, and processing configuration files.
"""

import os
import json
import re
import sys
from typing import Dict, Any, Optional
from pathlib import Path

# Try to import jsonschema, but provide fallback validation if not available
try:
    import jsonschema
    HAS_JSONSCHEMA = True
except ImportError:
    HAS_JSONSCHEMA = False
    print("Warning: jsonschema package not found. Using basic validation.", file=sys.stderr)


class ConfigError(Exception):
    """Exception raised for configuration errors."""
    pass


class ConfigHandler:
    """
    Handles loading and validating configuration for MCP Docker setup.
    """

    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize the configuration handler.
        
        Args:
            config_path: Path to the configuration file. If None, uses the CONFIG_PATH
                         environment variable or falls back to /app/config.json
        """
        self.config_path = config_path or os.environ.get('CONFIG_PATH', '/app/config.json')
        self.schema_path = os.path.join(os.path.dirname(__file__), 'config.schema.json')
        self.config = None
        self.schema = None

    def load_schema(self) -> Dict[str, Any]:
        """
        Load the JSON schema for configuration validation.
        
        Returns:
            The loaded schema as a dictionary
            
        Raises:
            ConfigError: If the schema file cannot be loaded or is invalid
        """
        try:
            if not os.path.exists(self.schema_path):
                # Try to find the schema in the current directory
                self.schema_path = 'config.schema.json'
                
            with open(self.schema_path, 'r') as f:
                self.schema = json.load(f)
                return self.schema
        except (json.JSONDecodeError, FileNotFoundError) as e:
            raise ConfigError(f"Failed to load schema: {str(e)}")

    def load_config(self) -> Dict[str, Any]:
        """
        Load the configuration from the specified file.
        
        Returns:
            The loaded configuration as a dictionary
            
        Raises:
            ConfigError: If the configuration file cannot be loaded or is invalid
        """
        try:
            config_path = Path(self.config_path)
            
            if not config_path.exists():
                # Check if example config exists and copy it
                example_path = Path(str(config_path).replace('.json', '.example.json'))
                if example_path.exists():
                    print(f"Configuration file {config_path} not found. Using example configuration.")
                    with open(example_path, 'r') as f:
                        self.config = json.load(f)
                else:
                    raise ConfigError(f"Configuration file {config_path} not found and no example configuration available.")
            else:
                with open(config_path, 'r') as f:
                    self.config = json.load(f)
            
            return self.config
        except json.JSONDecodeError as e:
            raise ConfigError(f"Invalid JSON in configuration file: {str(e)}")
        except FileNotFoundError:
            raise ConfigError(f"Configuration file not found: {self.config_path}")
        except PermissionError:
            raise ConfigError(f"Permission denied when reading configuration file: {self.config_path}")
        except Exception as e:
            raise ConfigError(f"Error loading configuration: {str(e)}")

    def validate_config(self, config: Optional[Dict[str, Any]] = None) -> bool:
        """
        Validate the configuration against the schema.
        
        Args:
            config: The configuration to validate. If None, uses the previously loaded config.
            
        Returns:
            True if the configuration is valid
            
        Raises:
            ConfigError: If the configuration is invalid
        """
        if config is None:
            config = self.config
            
        if config is None:
            raise ConfigError("No configuration loaded to validate")
            
        if self.schema is None:
            self.load_schema()
        
        if HAS_JSONSCHEMA:
            try:
                jsonschema.validate(instance=config, schema=self.schema)
                return True
            except jsonschema.exceptions.ValidationError as e:
                raise ConfigError(f"Configuration validation failed: {str(e)}")
        else:
            # Basic validation when jsonschema is not available
            return self._basic_validate(config, self.schema)
    
    def _basic_validate(self, instance: Dict[str, Any], schema: Dict[str, Any], path: str = "") -> bool:
        """
        Basic validation implementation when jsonschema is not available.
        
        Args:
            instance: The configuration instance to validate
            schema: The schema to validate against
            path: Current path in the configuration (for error messages)
            
        Returns:
            True if the configuration is valid
            
        Raises:
            ConfigError: If the configuration is invalid
        """
        # Check required properties
        if "required" in schema and isinstance(schema["required"], list):
            for prop in schema["required"]:
                if prop not in instance:
                    raise ConfigError(f"Missing required property '{prop}' at {path or 'root'}")
        
        # Check property types and validate nested objects
        if "properties" in schema and isinstance(schema["properties"], dict):
            for prop_name, prop_schema in schema["properties"].items():
                if prop_name in instance:
                    prop_path = f"{path}.{prop_name}" if path else prop_name
                    prop_value = instance[prop_name]
                    
                    # Check type
                    if "type" in prop_schema:
                        expected_type = prop_schema["type"]
                        if expected_type == "object" and not isinstance(prop_value, dict):
                            raise ConfigError(f"Property '{prop_path}' must be an object")
                        elif expected_type == "array" and not isinstance(prop_value, list):
                            raise ConfigError(f"Property '{prop_path}' must be an array")
                        elif expected_type == "string" and not isinstance(prop_value, str):
                            raise ConfigError(f"Property '{prop_path}' must be a string")
                        elif expected_type == "number" and not isinstance(prop_value, (int, float)):
                            raise ConfigError(f"Property '{prop_path}' must be a number")
                        elif expected_type == "boolean" and not isinstance(prop_value, bool):
                            raise ConfigError(f"Property '{prop_path}' must be a boolean")
                    
                    # Validate nested objects
                    if isinstance(prop_value, dict) and "properties" in prop_schema:
                        self._basic_validate(prop_value, prop_schema, prop_path)
                    
                    # Validate array items
                    if isinstance(prop_value, list) and "items" in prop_schema:
                        for i, item in enumerate(prop_value):
                            item_path = f"{prop_path}[{i}]"
                            if isinstance(item, dict) and isinstance(prop_schema["items"], dict):
                                self._basic_validate(item, prop_schema["items"], item_path)
        
        # Check additional properties
        if "additionalProperties" in schema and isinstance(instance, dict):
            if isinstance(schema["additionalProperties"], dict):
                for prop_name, prop_value in instance.items():
                    if "properties" not in schema or prop_name not in schema["properties"]:
                        prop_path = f"{path}.{prop_name}" if path else prop_name
                        if isinstance(prop_value, dict):
                            self._basic_validate(prop_value, schema["additionalProperties"], prop_path)
        
        return True

    def substitute_env_vars(self, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Substitute environment variables in the configuration.
        
        Args:
            config: The configuration to process. If None, uses the previously loaded config.
            
        Returns:
            The processed configuration with environment variables substituted
            
        Raises:
            ConfigError: If required environment variables are missing
        """
        if config is None:
            config = self.config
            
        if config is None:
            raise ConfigError("No configuration loaded for environment variable substitution")
            
        # Create a deep copy to avoid modifying the original
        processed_config = json.loads(json.dumps(config))
        
        # Process environment variables in the configuration
        env_var_pattern = re.compile(r'\${([A-Za-z0-9_]+)}')
        missing_vars = set()
        
        def process_value(value):
            if isinstance(value, str):
                matches = env_var_pattern.findall(value)
                result = value
                for var_name in matches:
                    env_value = os.environ.get(var_name)
                    if env_value is None:
                        missing_vars.add(var_name)
                    else:
                        result = result.replace(f"${{{var_name}}}", env_value)
                return result
            elif isinstance(value, dict):
                return {k: process_value(v) for k, v in value.items()}
            elif isinstance(value, list):
                return [process_value(item) for item in value]
            else:
                return value
        
        processed_config = process_value(processed_config)
        
        if missing_vars:
            raise ConfigError(f"Missing required environment variables: {', '.join(missing_vars)}")
            
        return processed_config

    def get_config(self) -> Dict[str, Any]:
        """
        Get the fully processed configuration.
        
        Returns:
            The processed configuration with environment variables substituted
            
        Raises:
            ConfigError: If the configuration cannot be loaded or processed
        """
        if self.config is None:
            self.load_config()
            
        self.validate_config()
        return self.substitute_env_vars()
        
    def merge_config(self, additional_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Merge additional configuration with the current configuration.
        
        Args:
            additional_config: Additional configuration to merge
            
        Returns:
            The merged configuration
            
        Raises:
            ConfigError: If the merged configuration is invalid
        """
        if self.config is None:
            self.load_config()
            
        # Deep merge the configurations
        merged_config = self._deep_merge(self.config, additional_config)
        
        # Validate the merged configuration
        old_config = self.config
        self.config = merged_config
        self.validate_config()
        
        return self.config
    
    def _deep_merge(self, base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
        """
        Deep merge two dictionaries.
        
        Args:
            base: Base dictionary
            override: Dictionary to override base values
            
        Returns:
            Merged dictionary
        """
        result = base.copy()
        
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value
                
        return result
    
    def write_config(self, config_path: Optional[str] = None) -> None:
        """
        Write the current configuration to a file.
        
        Args:
            config_path: Path to write the configuration to. If None, uses the current config_path.
            
        Raises:
            ConfigError: If the configuration cannot be written
        """
        if self.config is None:
            raise ConfigError("No configuration loaded to write")
            
        path = config_path or self.config_path
        
        try:
            with open(path, 'w') as f:
                json.dump(self.config, f, indent=2)
        except PermissionError:
            raise ConfigError(f"Permission denied when writing configuration file: {path}")
        except Exception as e:
            raise ConfigError(f"Error writing configuration: {str(e)}")
    
    def apply_defaults(self) -> Dict[str, Any]:
        """
        Apply default values from the schema to the configuration.
        
        Returns:
            The configuration with defaults applied
            
        Raises:
            ConfigError: If the schema cannot be loaded
        """
        if self.config is None:
            self.load_config()
            
        if self.schema is None:
            self.load_schema()
            
        # Apply defaults from the schema
        self.config = self._apply_schema_defaults(self.config, self.schema)
        
        return self.config
    
    def _apply_schema_defaults(self, config: Dict[str, Any], schema: Dict[str, Any]) -> Dict[str, Any]:
        """
        Apply default values from the schema to the configuration.
        
        Args:
            config: Configuration to apply defaults to
            schema: Schema with default values
            
        Returns:
            Configuration with defaults applied
        """
        result = config.copy()
        
        # Apply top-level defaults
        if "properties" in schema:
            for prop_name, prop_schema in schema["properties"].items():
                if prop_name not in result and "default" in prop_schema:
                    result[prop_name] = prop_schema["default"]
                    
                # Apply defaults to nested objects
                if prop_name in result and "properties" in prop_schema and isinstance(result[prop_name], dict):
                    result[prop_name] = self._apply_schema_defaults(result[prop_name], prop_schema)
                    
        # Apply defaults to additional properties
        if "additionalProperties" in schema and isinstance(schema["additionalProperties"], dict):
            for prop_name, prop_value in result.items():
                if "properties" not in schema or prop_name not in schema["properties"]:
                    if isinstance(prop_value, dict):
                        result[prop_name] = self._apply_schema_defaults(prop_value, schema["additionalProperties"])
                        
        return result


def load_and_validate_config(config_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Helper function to load and validate configuration.
    
    Args:
        config_path: Path to the configuration file
        
    Returns:
        The processed configuration
        
    Raises:
        SystemExit: If the configuration cannot be loaded or is invalid
    """
    try:
        handler = ConfigHandler(config_path)
        handler.load_config()
        handler.validate_config()
        return handler.get_config()
    except ConfigError as e:
        print(f"Configuration error: {str(e)}", file=sys.stderr)
        sys.exit(1)


def print_usage():
    """Print usage information."""
    print("Usage: config_handler.py [OPTIONS] [CONFIG_PATH]")
    print("\nOptions:")
    print("  --validate       Validate the configuration")
    print("  --apply-defaults Apply default values from the schema")
    print("  --output PATH    Write the processed configuration to PATH")
    print("  --merge PATH     Merge with additional configuration from PATH")
    print("  --help           Show this help message and exit")
    print("\nExamples:")
    print("  config_handler.py config.json")
    print("  config_handler.py --validate config.json")
    print("  config_handler.py --apply-defaults --output config_with_defaults.json config.json")
    print("  config_handler.py --merge override.json --output merged.json config.json")


if __name__ == "__main__":
    # Parse command line arguments
    args = sys.argv[1:]
    config_path = None
    output_path = None
    merge_path = None
    validate_only = False
    apply_defaults = False
    
    i = 0
    while i < len(args):
        arg = args[i]
        if arg == "--help":
            print_usage()
            sys.exit(0)
        elif arg == "--validate":
            validate_only = True
        elif arg == "--apply-defaults":
            apply_defaults = True
        elif arg == "--output" and i + 1 < len(args):
            output_path = args[i + 1]
            i += 1
        elif arg == "--merge" and i + 1 < len(args):
            merge_path = args[i + 1]
            i += 1
        elif not arg.startswith("--") and config_path is None:
            config_path = arg
        else:
            print(f"Unknown option: {arg}", file=sys.stderr)
            print_usage()
            sys.exit(1)
        i += 1
    
    try:
        # Create the configuration handler
        handler = ConfigHandler(config_path)
        
        # Load the configuration
        handler.load_config()
        
        # Validate the configuration
        handler.validate_config()
        
        # Apply defaults if requested
        if apply_defaults:
            handler.apply_defaults()
        
        # Merge with additional configuration if requested
        if merge_path:
            try:
                with open(merge_path, 'r') as f:
                    additional_config = json.load(f)
                handler.merge_config(additional_config)
            except json.JSONDecodeError as e:
                print(f"Error parsing merge configuration: {str(e)}", file=sys.stderr)
                sys.exit(1)
            except FileNotFoundError:
                print(f"Merge configuration file not found: {merge_path}", file=sys.stderr)
                sys.exit(1)
        
        # Process environment variables
        config = handler.get_config()
        
        # Write the configuration to a file if requested
        if output_path:
            handler.write_config(output_path)
            print(f"Configuration written to {output_path}")
        
        # Print the configuration if not validate-only
        if not validate_only:
            print(json.dumps(config, indent=2))
        else:
            print("Configuration is valid")
            
    except ConfigError as e:
        print(f"Configuration error: {str(e)}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {str(e)}", file=sys.stderr)
        sys.exit(1)