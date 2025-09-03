"""
Configuration Loader Module

Handles loading and validation of configuration files for the Tmux Orchestrator system.
"""

import json
import yaml
from pathlib import Path
from typing import Dict, Any, Optional, List, Union
from dataclasses import dataclass, field
from rich.console import Console

from .file_utils import FileUtils

console = Console()


@dataclass
class ConfigValidationRule:
    """Configuration validation rule."""
    field_path: str
    required: bool = True
    field_type: type = str
    default_value: Any = None
    allowed_values: Optional[List[Any]] = None
    min_value: Optional[Union[int, float]] = None
    max_value: Optional[Union[int, float]] = None


@dataclass
class ConfigSchema:
    """Configuration schema definition."""
    name: str
    version: str
    rules: List[ConfigValidationRule] = field(default_factory=list)
    
    def add_rule(self, **kwargs) -> 'ConfigSchema':
        """Add validation rule."""
        self.rules.append(ConfigValidationRule(**kwargs))
        return self


class ConfigLoader:
    """
    Configuration loader with validation and schema support.
    
    Features:
    - JSON and YAML configuration support
    - Schema validation with detailed error reporting
    - Environment variable substitution
    - Configuration merging and inheritance
    - Default value handling
    """
    
    def __init__(self, config_dir: Path):
        """
        Initialize config loader.
        
        Args:
            config_dir: Directory containing configuration files
        """
        self.config_dir = config_dir
        self.config_dir.mkdir(parents=True, exist_ok=True)
        
        # Cache for loaded configurations
        self._config_cache: Dict[str, Dict[str, Any]] = {}
        
        # Built-in schemas
        self._schemas: Dict[str, ConfigSchema] = {}
        self._initialize_builtin_schemas()
    
    def load_config(self, 
                   config_name: str,
                   schema_name: Optional[str] = None,
                   use_cache: bool = True,
                   required: bool = True) -> Optional[Dict[str, Any]]:
        """
        Load configuration file with optional schema validation.
        
        Args:
            config_name: Name of config file (without extension)
            schema_name: Name of schema to validate against
            use_cache: Whether to use cached config
            required: Whether config file is required
            
        Returns:
            Dict containing configuration or None if not found/invalid
        """
        # Check cache first
        if use_cache and config_name in self._config_cache:
            return self._config_cache[config_name]
        
        # Try to load from JSON first, then YAML
        config_data = None
        json_path = self.config_dir / f"{config_name}.json"
        yaml_path = self.config_dir / f"{config_name}.yaml"
        yml_path = self.config_dir / f"{config_name}.yml"
        
        if json_path.exists():
            config_data = FileUtils.read_json(json_path)
        elif yaml_path.exists():
            config_data = FileUtils.read_yaml(yaml_path)
        elif yml_path.exists():
            config_data = FileUtils.read_yaml(yml_path)
        
        if config_data is None:
            if required:
                console.print(f"[red]❌ Required config not found: {config_name}[/red]")
                return None
            else:
                console.print(f"[yellow]⚠️ Optional config not found: {config_name}[/yellow]")
                return {}
        
        # Perform environment variable substitution
        config_data = self._substitute_environment_variables(config_data)
        
        # Validate against schema if provided
        if schema_name:
            if not self.validate_config(config_data, schema_name):
                console.print(f"[red]❌ Config validation failed for {config_name}[/red]")
                return None
        
        # Cache the result
        if use_cache:
            self._config_cache[config_name] = config_data
        
        console.print(f"[green]✅ Loaded config: {config_name}[/green]")
        return config_data
    
    def save_config(self, 
                   config_name: str, 
                   config_data: Dict[str, Any],
                   format: str = "json") -> bool:
        """
        Save configuration to file.
        
        Args:
            config_name: Name of config file
            config_data: Configuration data to save
            format: File format ('json' or 'yaml')
            
        Returns:
            bool: True if save succeeded
        """
        try:
            if format.lower() == "json":
                file_path = self.config_dir / f"{config_name}.json"
                success = FileUtils.write_json(file_path, config_data)
            elif format.lower() in ["yaml", "yml"]:
                file_path = self.config_dir / f"{config_name}.yaml"
                success = FileUtils.write_yaml(file_path, config_data)
            else:
                console.print(f"[red]❌ Unsupported config format: {format}[/red]")
                return False
            
            if success:
                # Update cache
                self._config_cache[config_name] = config_data
                console.print(f"[green]✅ Saved config: {config_name} ({format})[/green]")
            
            return success
            
        except Exception as e:
            console.print(f"[red]❌ Error saving config {config_name}: {e}[/red]")
            return False
    
    def merge_configs(self, 
                     base_config: Dict[str, Any], 
                     override_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Merge two configuration dictionaries recursively.
        
        Args:
            base_config: Base configuration
            override_config: Configuration to merge in
            
        Returns:
            Merged configuration
        """
        merged = base_config.copy()
        
        for key, value in override_config.items():
            if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
                # Recursive merge for nested dictionaries
                merged[key] = self.merge_configs(merged[key], value)
            else:
                # Override value
                merged[key] = value
        
        return merged
    
    def register_schema(self, schema: ConfigSchema) -> None:
        """
        Register a configuration schema.
        
        Args:
            schema: Schema to register
        """
        self._schemas[schema.name] = schema
        console.print(f"[green]✅ Registered schema: {schema.name} (v{schema.version})[/green]")
    
    def validate_config(self, config_data: Dict[str, Any], schema_name: str) -> bool:
        """
        Validate configuration against schema.
        
        Args:
            config_data: Configuration to validate
            schema_name: Name of schema to validate against
            
        Returns:
            bool: True if validation passed
        """
        if schema_name not in self._schemas:
            console.print(f"[red]❌ Schema not found: {schema_name}[/red]")
            return False
        
        schema = self._schemas[schema_name]
        validation_errors = []
        
        for rule in schema.rules:
            try:
                value = self._get_nested_value(config_data, rule.field_path)
                
                # Check if field exists and is required
                if value is None:
                    if rule.required:
                        validation_errors.append(f"Required field missing: {rule.field_path}")
                    elif rule.default_value is not None:
                        # Set default value
                        self._set_nested_value(config_data, rule.field_path, rule.default_value)
                    continue
                
                # Type validation
                if not isinstance(value, rule.field_type):
                    validation_errors.append(
                        f"Field {rule.field_path} must be {rule.field_type.__name__}, got {type(value).__name__}"
                    )
                    continue
                
                # Value constraints
                if rule.allowed_values and value not in rule.allowed_values:
                    validation_errors.append(
                        f"Field {rule.field_path} must be one of {rule.allowed_values}, got {value}"
                    )
                
                if rule.min_value is not None and value < rule.min_value:
                    validation_errors.append(
                        f"Field {rule.field_path} must be >= {rule.min_value}, got {value}"
                    )
                
                if rule.max_value is not None and value > rule.max_value:
                    validation_errors.append(
                        f"Field {rule.field_path} must be <= {rule.max_value}, got {value}"
                    )
                
            except Exception as e:
                validation_errors.append(f"Validation error for {rule.field_path}: {e}")
        
        if validation_errors:
            console.print(f"[red]❌ Config validation failed for schema {schema_name}:[/red]")
            for error in validation_errors:
                console.print(f"[red]  • {error}[/red]")
            return False
        
        console.print(f"[green]✅ Config validation passed for schema {schema_name}[/green]")
        return True
    
    def get_config_value(self, 
                        config_name: str, 
                        field_path: str, 
                        default: Any = None) -> Any:
        """
        Get specific value from configuration.
        
        Args:
            config_name: Name of config file
            field_path: Dot-separated path to field (e.g., 'database.host')
            default: Default value if field not found
            
        Returns:
            Configuration value or default
        """
        config = self.load_config(config_name, required=False)
        if not config:
            return default
        
        value = self._get_nested_value(config, field_path)
        return value if value is not None else default
    
    def set_config_value(self, 
                        config_name: str, 
                        field_path: str, 
                        value: Any,
                        save: bool = True) -> bool:
        """
        Set specific value in configuration.
        
        Args:
            config_name: Name of config file
            field_path: Dot-separated path to field
            value: Value to set
            save: Whether to save config after setting
            
        Returns:
            bool: True if value was set successfully
        """
        config = self.load_config(config_name, required=False)
        if config is None:
            config = {}
        
        self._set_nested_value(config, field_path, value)
        
        # Update cache
        self._config_cache[config_name] = config
        
        if save:
            return self.save_config(config_name, config)
        
        return True
    
    def clear_cache(self) -> None:
        """Clear configuration cache."""
        self._config_cache.clear()
        console.print("[green]✅ Configuration cache cleared[/green]")
    
    def _get_nested_value(self, data: Dict[str, Any], path: str) -> Any:
        """Get nested value using dot notation."""
        keys = path.split('.')
        current = data
        
        for key in keys:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return None
        
        return current
    
    def _set_nested_value(self, data: Dict[str, Any], path: str, value: Any) -> None:
        """Set nested value using dot notation."""
        keys = path.split('.')
        current = data
        
        for key in keys[:-1]:
            if key not in current:
                current[key] = {}
            current = current[key]
        
        current[keys[-1]] = value
    
    def _substitute_environment_variables(self, data: Any) -> Any:
        """Recursively substitute environment variables in configuration."""
        import os
        import re
        
        if isinstance(data, dict):
            return {k: self._substitute_environment_variables(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [self._substitute_environment_variables(item) for item in data]
        elif isinstance(data, str):
            # Replace ${VAR_NAME} or $VAR_NAME patterns
            def replace_env_var(match):
                var_name = match.group(1) or match.group(2)
                return os.environ.get(var_name, match.group(0))
            
            # Pattern for ${VAR} or $VAR
            pattern = r'\$\{([A-Za-z_][A-Za-z0-9_]*)\}|\$([A-Za-z_][A-Za-z0-9_]*)'
            return re.sub(pattern, replace_env_var, data)
        else:
            return data
    
    def _initialize_builtin_schemas(self) -> None:
        """Initialize built-in configuration schemas."""
        
        # Orchestrator configuration schema
        orchestrator_schema = ConfigSchema("orchestrator", "1.0")
        orchestrator_schema.add_rule(
            field_path="oauth.port",
            required=True,
            field_type=int,
            default_value=3000,
            min_value=1024,
            max_value=65535
        ).add_rule(
            field_path="oauth.timeout_seconds",
            required=True,
            field_type=int,
            default_value=45,
            min_value=30,
            max_value=120
        ).add_rule(
            field_path="tmux.session_prefix",
            required=True,
            field_type=str,
            default_value="tmux-orc"
        ).add_rule(
            field_path="agents.default_check_in_minutes",
            required=True,
            field_type=int,
            default_value=45,
            min_value=5,
            max_value=180
        ).add_rule(
            field_path="logging.level",
            required=True,
            field_type=str,
            default_value="INFO",
            allowed_values=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        )
        
        self.register_schema(orchestrator_schema)
        
        # Agent configuration schema
        agent_schema = ConfigSchema("agent", "1.0")
        agent_schema.add_rule(
            field_path="role",
            required=True,
            field_type=str
        ).add_rule(
            field_path="window_index",
            required=True,
            field_type=int,
            min_value=0
        ).add_rule(
            field_path="check_in_interval",
            required=True,
            field_type=int,
            default_value=45,
            min_value=5,
            max_value=180
        ).add_rule(
            field_path="responsibilities",
            required=True,
            field_type=list
        ).add_rule(
            field_path="mcp_enabled",
            required=True,
            field_type=bool,
            default_value=True
        )
        
        self.register_schema(agent_schema)
        
        # System monitoring schema
        monitoring_schema = ConfigSchema("monitoring", "1.0")
        monitoring_schema.add_rule(
            field_path="thresholds.cpu_warning",
            required=True,
            field_type=float,
            default_value=80.0,
            min_value=50.0,
            max_value=95.0
        ).add_rule(
            field_path="thresholds.memory_warning",
            required=True,
            field_type=float,
            default_value=85.0,
            min_value=50.0,
            max_value=95.0
        ).add_rule(
            field_path="collection_interval",
            required=True,
            field_type=int,
            default_value=60,
            min_value=30,
            max_value=300
        ).add_rule(
            field_path="retention_hours",
            required=True,
            field_type=int,
            default_value=168,  # 1 week
            min_value=24,
            max_value=720
        )
        
        self.register_schema(monitoring_schema)