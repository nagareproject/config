==================
Configuration file
==================

Overview
========

The ``nagare-config`` package provides a powerful configuration file parser for Python applications, inspired by the
ConfigObj library. It enables loading, parsing, validating, and interpolating configuration values from various sources
in a flexible and robust way.

This module allows you to work with hierarchical configuration files, validate your configuration against
specifications, and build complex configuration structures programmatically.

Key Features
============

* **Hierarchical Configuration**: Support for nested sections to any depth
* **Value Interpolation**: Reference other configuration values using variable substitution with ``$variable`` or
  ${variable}`` syntax
* **Type Validation**: Validate configuration values against specifications for type checking and conversion
* **Default Values**: Define default values for optional configuration parameters
* **Configuration Merging**: Combine multiple configuration sources recursively
* **Multiline Values**: Support for multi-line string values with triple quotes
* **Comments Support**: Preserve comments in configuration files
* **List Values**: Native support for lists in configuration files
* **String Escaping**: Proper handling of quotes and special characters

Installation
============

.. code-block:: bash

    pip install nagare-config

Basic Usage
===========

Loading Configuration
---------------------

.. code-block:: python

    from nagare.config import config_from_string, config_from_file, config_from_dict

    # Load from a string
    config = config_from_string("""
    app_name = MyApp
    debug = true

    [database]
    host = localhost
    port = 5432
    username = dbuser
    password = secret
    """)

    # Load from a file
    config = config_from_file('config.cfg')

    # Load from a dictionary
    config = config_from_dict({
        'app_name': 'MyApp',
        'database': {
            'host': 'localhost',
            'port': 5432
        }
    })

Accessing Configuration Values
------------------------------

Configuration values can be accessed using dictionary-style notation:

.. code-block:: python

    # Access top-level values
    app_name = config['app_name']

    # Access nested values
    db_host = config['database']['host']
    db_port = config['database']['port']

    # Using get() with default values
    debug = config.get('debug', False)

Modifying Configuration
-----------------------

.. code-block:: python

    # Set values
    config['app_name'] = 'NewAppName'

    # Add a section
    config['logging'] = {}
    config['logging']['level'] = 'INFO'
    config['logging']['file'] = '/var/log/app.log'

    # Create nested sections
    config['api'] = {}
    config['api']['version'] = 'v1'
    config['api']['endpoint'] = {}
    config['api']['endpoint']['url'] = 'https://api.example.com'

Variable Interpolation
----------------------

Configuration values can reference other values using the ``$`` symbol:

.. code-block:: python

    # Configuration with variables
    config_text = """
    data_dir = /var/data
    log_dir = ${data_dir}/logs

    [app]
    name = MyApp
    config_file = ${data_dir}/${name}.conf
    """

    # Load and interpolate
    config = config_from_string(config_text)
    config.interpolate()

    # Now config['log_dir'] == '/var/data/logs'
    # and config['app']['config_file'] == '/var/data/MyApp.conf'

Validation with Specifications
------------------------------

You can validate your configuration against a specification for type checking and defaults:

.. code-block:: python

    from nagare.config import config_from_string
    from nagare.validate import Validator

    # Define a specification
    spec_text = """
    debug = boolean(default=false)
    port = integer(min=1024, max=65535, default=8080)

    [database]
    host = string(default="localhost")
    port = integer(default=5432)
    username = string
    password = string
    pool_size = integer(min=1, default=5)
    """

    # Parse the specification
    spec = config_from_string(spec_text)

    # Load and validate configuration
    config = config_from_string("""
    debug = true

    [database]
    username = dbuser
    password = secret
    """)

    # Create validator
    validator = Validator()

    # Add defaults from the specification
    config.merge_defaults(spec)

    # Validate against the specification
    result = config.validate(spec, validator)

    if result is True:
        print("Configuration is valid")
    else:
        print("Validation failed")

Configuration Syntax
====================

Basic Syntax
------------

.. code-block:: ini

    # This is a comment
    key = value  # This is an inline comment

    # Section
    [section_name]
    key1 = value1
    key2 = value2

    # Nested section
    [[nested_section]]
    key3 = value3

Value Types
-----------

.. code-block:: ini

    # String values (quotes optional in most cases)
    string1 = value
    string2 = "quoted value"
    string3 = 'single quoted value'

    # Boolean values
    bool1 = true   # true, yes, on, 1
    bool2 = false  # false, no, off, 0

    # Numeric values
    integer = 42
    float = 3.14

    # List values
    list1 = value1, value2, value3
    list2 = "quoted value", another value, 'single quoted'

    # Multiline string values
    multiline = """This is a
    multiline value
    spanning multiple lines"""

Variable Interpolation
----------------------

.. code-block:: ini

    # Simple variable reference
    base_dir = /var/data
    log_dir = $base_dir/logs

    # Variable reference with braces
    backup_dir = ${base_dir}/backups

    # Default value if variable is not defined
    temp_dir = ${temp_base:/tmp}/myapp

    # Reference values in sections
    [app]
    name = MyApp
    log_file = ${/log_dir}/${name}.log

Differences from ConfigObj
==========================

While nagare-config is inspired by ConfigObj, it has some differences in design and implementation:

1. Modern Python support with clean code design
2. Simplified API focused on the most common use cases
3. Different validation system tailored for Nagare framework needs
4. Performance optimizations for common operations

API Reference
==============

Main Functions
--------------

- **config_from_dict(d)**: Create a configuration from a dictionary
- **config_from_iter(lines, global_config=None, max_depth=0)**: Load configuration from an iterator of lines
- **config_from_file(filename, global_config=None, max_depth=0)**: Load configuration from a file
- **config_from_string(string, global_config=None, max_depth=0)**: Load configuration from a string

Section Methods
---------------

- **merge(config)**: Recursively merge with another configuration
- **interpolate(global_config=None)**: Perform variable interpolation
- **merge_defaults(spec, validator=None)**: Add default values from a specification
- **validate(spec, validator=None)**: Validate against a specification
- **display(indent=0, level=0)**: Print the configuration in a readable format
