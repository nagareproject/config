# --
# Copyright (c) 2014-2026 Net-ng.
# All rights reserved.
#
# This software is licensed under the BSD License, as described in
# the file LICENSE.txt, which you should have received as part of
# this distribution.
# --

"""Configuration File Parser Module.

This module provides a powerful configuration file parser that supports hierarchical
sections, variable interpolation, type validation, and complex configuration structures.
It's inspired by ConfigObj but designed specifically for the Nagare framework.

Key Features:
- Hierarchical configuration with nested sections
- Variable interpolation using $variable or ${variable} syntax
- Type validation and conversion
- Multi-line string values
- List support with automatic parsing
- Configuration merging and default values
- Comments preservation
- Comprehensive error reporting with line numbers

Example:
    from nagare.config import config_from_string, config_from_file

    # Load from string
    config = config_from_string('''
    app_name = MyApp
    debug = true

    [database]
    host = localhost
    port = 5432
    ''')

    # Access values
    app_name = config['app_name']  # 'MyApp'
    db_host = config['database']['host']  # 'localhost'
"""

import re
from typing import Any, Callable, Iterator, Optional, Sequence

from .validate import NO_DEFAULT, Validator
from .config_exceptions import (  # noqa: F401
    ParseError,
    ConfigError,
    SectionError,
    DirectiveError,
    ParameterError,
    InterpolationError,
    SpecificationError,
)

# Type aliases for better code readability
ConfigDict = dict[str, Any]
AncestorNames = tuple[str, ...]
Ancestors = tuple['Section', ...]
LineIterator = Iterator[str]

# Quote characters used in configuration files
QUOTES = ('"', "'")

# Regular expression for parsing list tails (comma-separated values)
TAIL = re.compile(
    r"""
    \s*,\s*                    # Optional whitespace, comma, optional whitespace
    (
       (?P<tail1>"[^"]*")      # Double-quoted value
       |
       (?P<tail2>'[^']*')      # Single-quoted value
       |
       (?:[^"',\s]*)           # Unquoted value (no quotes, commas, or whitespace)
    )
""",
    re.VERBOSE,
)

# Regular expression for parsing a value or a list of values
VALUE = re.compile(
    r"""
    (?P<value>
        (?P<head>("[^"]*")|('[^']*')|([^'"]*?))  # First value (quoted or unquoted)
        (?P<tail>{})*                             # Optional tail values
    )
""".format(TAIL.pattern),
    re.VERBOSE,
)

# Match complete value patterns
FULL_VALUE = re.compile('^{}$'.format(VALUE.pattern), re.VERBOSE)

# Comprehensive regular expression for parsing configuration file lines
LINE = re.compile(
    r'''^
    \s*                                          # Optional leading whitespace
    (
        (\#.*)                                   # -- Comment only line --
        |
        (                                        # -- Section --
            (?P<section_in>\[+)                  # Opening section brackets
            \s*
            (?P<section>                         # Section name
                ("[^"]+")|('[^']+')              # Quoted section name
                |
                (\$\((?P<section_directive>[^ ]+)(\ (?P<section_directive_args>[^)]+))?\))  # Directive
                |
                ([^'"]+?)                        # Unquoted section name
            )
            \s*
            (?P<section_out>\]+)                 # Closing section brackets
            \s*
            (\#?.*)                              # Optional comment
        )
        |
        (                                         # -- Parameter --
            (?P<name>("[^"]+")|('[^']+')|([^'"]+?))  # Parameter name
            \s*=\s*                              # Equals sign with optional whitespace
            (
                (
                    (?P<multi_delimiter_start>(\''')|("""))  # Multi-line delimiter start
                    (?P<multi>.*?)               # Multi-line content
                    (?P<multi_delimiter_end>(?P=multi_delimiter_start))?  # Multi-line delimiter end
                )|{}                             # Or single-line value
            )
       )
       \s*(\#.*)?                                # Optional trailing comment
    )?
    $
'''.format(VALUE.pattern),
    re.VERBOSE,
)

# Regular expression for variable interpolation
INTERPOLATION = re.compile(
    r"""
    \$                                           # Dollar sign prefix
    (
        (?P<escaped>\$)                          # Escaped dollar sign ($$)
        |
        (?P<named>[_a-zA-Z0-9]+)                # Simple variable name
        |
        (
            {                                    # Opening brace
                (?P<braced>[^:}]+)              # Variable name within braces
                (:                               # Optional default value separator
                    (?P<default>                 # Default value
                        (
                            (\${[^}]+})          # Nested variable reference
                            |
                            .                    # Any other character
                        )*
                    )
                )?
            }                                    # Closing brace
        )
    )
""",
    re.VERBOSE,
)

# Match complete interpolation patterns
FULL_INTERPOLATION = re.compile('^{}$'.format(INTERPOLATION.pattern), re.VERBOSE)


class Section(dict):
    """A configuration section that supports hierarchical structure and validation.

    A section has g nested sections, interpolation, validation, and merging capabilities.

    Example:
        section = Section()

        section['key'] = 'value'
        section.sections['subsection'] = Section()
        section.sections['subsection']['nested_key'] = 'nested_value'
    """

    def __init__(self, *args: Sequence[tuple[str, Any]], **kw: dict[str, Any]) -> None:
        """Initialize a new Section instance.

        Args:
            *args: Arguments passed to dict constructor
            **kw: Keyword arguments passed to dict constructor
        """
        super().__init__(*args, **kw)
        # Dictionary to store nested sections
        self.sections: dict[str, 'Section'] = {}

    def __bool__(self) -> bool:
        """Return True if the section contains any parameters or subsections (aka is not empty).

        Returns:
            True if the section has content, False otherwise
        """
        return bool(super()) or bool(self.sections)

    def __getitem__(self, k: str) -> Any:
        """Get a parameter or section by key.

        First checks for parameters in the current section, then checks
        for nested sections.

        Args:
            k: The key to retrieve

        Returns:
            The value associated with the key

        Raises:
            KeyError: If the key is not found in parameters or sections
        """
        return super().__getitem__(k) if k in self else self.sections[k]

    def get(self, k: str, default: Any = None) -> Any:
        """Get a parameter or section by key with a default value.

        Args:
            k: The key to retrieve
            default: Default value if key is not found

        Returns:
            The value associated with the key or the default value
        """
        return self.__getitem__(k) if k in self else self.sections.get(k, default)

    def pop(self, k: str, default: Any = None) -> Any:
        """Remove and return a parameter or section by key.

        Args:
            k: The key to remove
            default: Default value if key is not found

        Returns:
            The removed value or the default value
        """
        return super().pop(k) if k in self else self.sections.pop(k, default)

    def dict(self) -> ConfigDict:
        """Convert the section to a plain dictionary.

        Recursively converts all nested sections to dictionaries as well.

        Returns:
            A plain dictionary representation of the section
        """
        return dict(self) | {k: v.dict() for k, v in self.sections.items()}

    def merge(self, config: 'Section') -> 'Section':
        """Merge another configuration section into this one.

        Recursively merges nested sections. Parameters in the other
        configuration will override parameters in this one.

        Args:
            config: The configuration section to merge

        Returns:
            This section (for method chaining)
        """
        # Update parameters from the other config
        self.update(config)

        # Recursively merge nested sections
        for name, section in config.sections.items():
            # Get existing section or create new one, then merge
            self.sections[name] = self.sections.get(name, Section()).merge(section)

        return self

    def display(
        self, indent: int = 0, level: int = 0, filter_parameter: Callable[[str], bool] = lambda parameter: True
    ) -> None:
        """Display the configuration in a human-readable format.

        Prints the configuration to stdout with proper indentation and
        section headers.

        Args:
            indent: Number of spaces per indentation level
            level: Current nesting level (used internally)
            filter_parameter: Function to filter which parameters to display
        """
        spaces = ' ' * (indent * level)

        # Display parameters
        for k, v in sorted(self.items(), key=lambda param: (param[0] == '___many___', param[0])):
            if filter_parameter(k):
                print(spaces + k + ' = ' + repr(v))

        # Display nested sections
        for k, v in sorted(self.sections.items(), key=lambda section: (section[0] == '__many__', section)):
            if filter_parameter(k):
                print('')
                print(spaces + ('[' * (level + 1)) + k + (']' * (level + 1)))
                v.display(indent, level + 1, filter_parameter)

    # Parsing Methods
    # ---------------

    def from_dict(self, d: ConfigDict) -> 'Section':
        """Populate the section from a dictionary.

        Recursively converts nested dictionaries to Section instances.

        Args:
            d: Dictionary to convert

        Returns:
            This section (for method chaining)
        """
        for k, v in d.items():
            if isinstance(v, dict):
                # Convert nested dictionaries to Section instances
                self.sections[k] = Section().from_dict(v)
            else:
                # Store regular values as parameters
                self[k] = v

        return self

    @staticmethod
    def strip_quotes(v: str) -> str:
        """Remove surrounding quotes from a string value.

        Handles both single and double quotes.

        Args:
            v: String that may have surrounding quotes

        Returns:
            String with quotes removed
        """
        if v.startswith(QUOTES):
            v = v[1:]

        if v.endswith(QUOTES):
            v = v[:-1]

        return v

    @classmethod
    def _parse_value(
        cls, value: str, head: str, tail: str, tail1: Optional[str], tail2: Optional[str], **kw: Any
    ) -> str | list[str]:
        """Internal method to parse configuration values.

        Handles both single value and comma-separated list of values

        Args:
            value: The complete value string
            head: The first part of the value
            tail: The remaining parts (for lists)
            tail1: Double-quoted tail values
            tail2: Single-quoted tail values
            **kw: Additional parsed components (ignored)

        Returns:
            Either a single string value or a list of strings
        """
        if not tail:
            # Single value - remove quotes if present
            return cls.strip_quotes(head)

        # List value - parse comma-separated elements
        if head.startswith(QUOTES) or tail1 or tail2:
            return [cls.strip_quotes(e) for e, _, _ in TAIL.findall(',' + value)]

        return value

    @classmethod
    def parse_value(cls, value: str) -> str | list[str]:
        """Parse a configuration value string.

        Public interface for value parsing that handles both single
        values and comma-separated lists.

        Args:
            value: The value string to parse

        Returns:
            Either a single string or a list of strings
        """
        match = FULL_VALUE.match(value)
        if not match:
            return value
        return cls._parse_value(**match.groupdict())

    @staticmethod
    def parse_multilines(lines: LineIterator, nb_lines: int, value: str, end: str) -> tuple[int, str]:
        """Parse multi-line string values.

        Continues reading lines until the closing delimiter is found.

        Args:
            lines: Iterator of configuration file lines
            nb_lines: Current line number
            value: Initial value content
            end: Closing delimiter to look for

        Returns:
            Tuple of (final_line_number, complete_multiline_value)

        Raises:
            ParseError: If the closing delimiter is not found
        """
        start_line = nb_lines
        # Pattern to match lines with optional closing delimiter
        line_pattern = re.compile(r'^(?P<value>.*?)(?P<delimiter>{}\s*(#.*)?)?$'.format(end))

        for line in lines:
            nb_lines += 1
            m = line_pattern.match(line[:-1])  # Remove newline
            if m:
                value += '\n' + m.group('value')
                if m.group('delimiter'):
                    # Found closing delimiter
                    break
        else:
            # Iterator exhausted without finding delimiter
            raise ParseError('no multiline value end found', start_line)

        return nb_lines, value

    def from_iter(
        self,
        lines: LineIterator,
        global_config: Optional[ConfigDict] = None,
        max_depth: int = 0,
        ancestors: Ancestors = (),
        ancestors_names: AncestorNames = (),
        nb_lines: int = 0,
    ) -> 'Section':
        """Parse configuration from an iterator of lines.

        This is the core parsing method that processes configuration file
        syntax line by line.

        Args:
            lines: Iterator of configuration file lines
            global_config: Global configuration for interpolation
            max_depth: Maximum nesting depth (0 = unlimited)
            ancestors: Tuple of parent sections
            ancestors_names: Tuple of parent section names
            nb_lines: Starting line number

        Returns:
            This section (for method chaining)

        Raises:
            ParseError: If a line cannot be parsed
            SectionError: If section structure is invalid
            DirectiveError: If an unsupported directive is used
            ParameterError: If parameter names are duplicated
        """
        for line in lines:
            nb_lines += 1
            x = LINE.match(line.rstrip())
            if not x:
                raise ParseError("invalid line '{}'".format(line.strip()), nb_lines)

            m = x.groupdict()

            # Handle section definitions
            # --------------------------

            if m['section']:
                name = self.strip_quotes(m['section'])

                # Calculate section nesting level, which is the number of leading `[`
                level = len(m['section_in'])
                if len(m['section_out']) != level:  # Must have the same number of trailing `]`
                    raise SectionError('cannot compute the section depth', nb_lines, ancestors_names, name)

                # Check maximum depth limit of nested sections
                if max_depth and (level >= max_depth):
                    return self

                # Determine parent section
                if level == (len(ancestors) + 1):
                    # Direct child section
                    parent = self
                    section_ancestors = ancestors
                    section_ancestors_names = ancestors_names
                elif level <= len(ancestors):
                    # Sibling or uncle section - trim ancestors
                    ancestors = ancestors[:level]
                    parent = ancestors[-1]
                    section_ancestors = ancestors[:-1]
                    section_ancestors_names = ancestors_names[: level - 1]
                else:
                    # Section is too deeply nested
                    raise SectionError('section too nested', nb_lines, ancestors_names, name)

                # Handle section directives (currently not supported)
                directive = m.get('section_directive')
                if not directive:
                    # Check for duplicate section names
                    if (name in parent) or (name in parent.sections):
                        raise SectionError('duplicate section name', nb_lines, section_ancestors_names, name)

                    # Create and parse the new section
                    parent.sections[name] = Section()
                    parent.sections[name].from_iter(
                        lines,
                        global_config,
                        max_depth,
                        section_ancestors + (parent,),
                        section_ancestors_names + (name,),
                        nb_lines,
                    )
                else:
                    raise DirectiveError('invalid directive', nb_lines, ancestors_names, directive)

            # Handle parameter definitions
            # ----------------------------

            if m['name']:
                name = self.strip_quotes(m['name'])

                # Check for duplicate parameter names
                if (name in self) or (name in self.sections):
                    raise ParameterError('duplicate parameter name', nb_lines, ancestors_names, name)

                # Handle multi-line values
                if m['multi_delimiter_start']:
                    if m['multi_delimiter_end']:
                        # Complete multi-line value on single line
                        value = m['multi']
                    else:
                        # Multi-line value on several lines
                        nb_lines, value = self.parse_multilines(lines, nb_lines, m['multi'], m['multi_delimiter_start'])
                else:
                    # Single-line value
                    value = self._parse_value(**m)

                self[name] = value

        return self

    # Variable Interpolation Methods
    # ------------------------------

    def get_parameter(self, names: list[str]) -> tuple[Ancestors, Optional['Section'], Any]:
        """Get a parameter by navigating through nested sections.

        Follows a path like ['database', 'connection', 'host'], starting from this section,
        to find the parameter in deeply nested descendant sections.

        Args:
            names: List of section/parameter names forming a path

        Returns:
            Tuple of (ancestors_list, containing_section, parameter_value)
        """
        ancestors: Ancestors

        name = names.pop(0)
        if names:
            # More names in path - recurse into subsection
            ancestors, section, value = (), None, self.sections.get(name)
            if value:
                ancestors, section, value = value.get_parameter(names)
                ancestors = (self,) + ancestors
        else:
            # Last name in path - get parameter value
            ancestors, section, value = (self,), self, self.get(name)

        return ancestors, section, value

    def find_parameter(
        self, name: str, ancestors: Sequence['Section'], global_config: ConfigDict
    ) -> tuple[Optional['Section'], Any]:
        """Find a parameter by looking up the section hierarchy.

        Looks for the parameter in this section, then parent sections,
        then global configuration.

        Args:
            name: Parameter name to find
            ancestors: List of ancestor sections to search
            global_config: Global configuration dictionary

        Returns:
            Tuple of (containing_section, parameter_value)
        """
        section: Optional['Section']

        section, value = self, self.get(name)  # Lookup in this section
        if value is None:
            if ancestors:
                # Search in parent sections
                section, value = ancestors[-1].find_parameter(name, ancestors[:-1], global_config)
            else:
                # This section is the root of the configuration. Now search in global configuration
                section, value = None, global_config.get(name)

        return section, value

    def _interpolate(
        self,
        ancestors: Ancestors,
        ancestors_names: AncestorNames,
        name: str,
        global_config: ConfigDict,
        refs: list[tuple[int, str]],
        escaped: Optional[str],
        named: Optional[str],
        braced: Optional[str],
        default: Optional[str],
    ) -> tuple[Optional[str], Any]:
        """Internal method for variable interpolation.

        Handles the core logic of resolving variable references like
        $variable or ${variable:default}. Internal method directly called
        with the ``INTERPOLATION`` regexp matching parameters

        Args:
            ancestors: List of ancestor sections for scoping
            ancestors_names: Names of ancestor sections for error reporting
            name: Name of the parameter being interpolated
            global_config: Global configuration for variable lookup
            refs: List of reference chains to detect circular dependencies
            escaped: Escaped dollar sign ($$)
            named: Simple variable name ($variable)
            braced: Braced variable name (${variable})
            default: Default value if variable not found

        Returns:
            Tuple of (parameter_name, resolved_value)

        Raises:
            InterpolationError: If variable not found or circular reference detected
        """
        if escaped:
            # Handle escaped dollar sign
            return None, '$'

        # Get the variable name (either simple or braced form)
        parameter_name = named or braced or ''

        if parameter_name.count('/') == 0:
            # Simple variable name - search from current scope
            section, value = self.find_parameter(parameter_name, ancestors, global_config)
        else:
            # Absolute path reference (starts with /) - follow path starting from the configuration root
            if ancestors:
                parameter_name = parameter_name.strip('/')
                ancestors, section, value = ancestors[0].get_parameter(parameter_name.split('/'))
            else:
                section = None
                value = None

        # Use default value if variable not found
        if (value is None) and (default is not None):
            value = self.parse_value(default)

        if value is None:
            raise InterpolationError(
                'variable {} not found'.format(repr(parameter_name)), sections=ancestors_names, name=name
            )

        # Check for circular references
        ref = id(section), parameter_name
        if ref in refs:
            loop = [repr(r[1]) for r in refs]
            raise InterpolationError(
                'interpolation loop {} detected'.format(' -> '.join(loop)), sections=ancestors_names
            )

        # Recursively interpolate the resolved value
        value = self.interpolate_parameter(value, ancestors, ancestors_names, name, global_config, refs + [ref])

        # Lists cannot be interpolated into strings
        if isinstance(value, list):
            raise InterpolationError(
                'variable {} is list {}'.format(repr(parameter_name), repr(value)), sections=ancestors_names, name=name
            )

        return parameter_name, value

    def _interpolate_parameter(
        self,
        ancestors: Ancestors,
        ancestors_names: AncestorNames,
        name: str,
        global_config: ConfigDict,
        refs: list[tuple[int, str]],
        **match: Any,
    ) -> str:
        """Helper method for parameter interpolation.

        Wrapper around _interpolate that ensures the result is a string
        suitable for substitution.

        Args:
            ancestors: List of ancestor sections
            ancestors_names: Names of ancestor sections
            name: Parameter name being interpolated
            global_config: Global configuration
            refs: Reference chain for circular dependency detection
            **match: Regex match groups

        Returns:
            The interpolated string value

        Raises:
            InterpolationError: If the resolved value is a list
        """
        var_name, value = self._interpolate(ancestors, ancestors_names, name, global_config, refs, **match)
        if isinstance(value, list):
            raise InterpolationError(
                'variable {} is list {}'.format(repr(var_name), repr(value)), sections=ancestors_names, name=name
            )

        return str(value)

    def interpolate_parameter(
        self,
        value: str | list[str],
        ancestors: Ancestors,
        ancestors_names: AncestorNames,
        name: str,
        global_config: ConfigDict,
        refs: list[tuple[int, str]],
    ) -> str | list[str]:
        """Interpolate variables in a parameter value.

        Handles both single string values and lists of strings.

        Args:
            value: The value to interpolate (string or list)
            ancestors: List of ancestor sections
            ancestors_names: Names of ancestor sections
            name: Parameter name
            global_config: Global configuration
            refs: Reference chain for circular dependency detection

        Returns:
            The value with all variables interpolated
        """
        is_list = isinstance(value, list)

        def interpolate(match: re.Match) -> str:
            """Interpolation function for regex substitution."""
            return self._interpolate_parameter(
                ancestors, ancestors_names, name, global_config, refs, **match.groupdict()
            )

        # Process each element (or the single value)
        value = [
            INTERPOLATION.sub(interpolate, e) if isinstance(e, str) else e  # type: ignore
            for e in (value if is_list else [value])
        ]

        return value if is_list else value[0]

    def interpolate_section(
        self,
        name: str,
        ancestors: Ancestors,
        ancestors_names: AncestorNames,
        global_config: ConfigDict,
        refs: list[tuple[int, str]],
    ) -> tuple[str, 'Section']:
        """Interpolate variables in section names.

        Allows section names to contain variable references that are
        resolved during interpolation.

        Args:
            name: Section name (may contain variables)
            ancestors: List of ancestor sections
            ancestors_names: Names of ancestor sections
            global_config: Global configuration
            refs: Reference chain for circular dependency detection

        Returns:
            Tuple of (resolved_section_name, section_object)
        """
        match = FULL_INTERPOLATION.match(name)
        if match:
            # Section name is entirely a variable reference
            new_name, value = self._interpolate(
                ancestors, ancestors_names, name, global_config, refs, **match.groupdict()
            )
            if isinstance(value, Section):
                # Variable resolves to a section - interpolate it too
                value.interpolate(global_config, ancestors, ancestors_names)
                new_name = (new_name or '').split('/')[-1]
            else:
                # Variable resolves to a value - create empty section
                new_name, value = value, config_from_dict({})
        else:
            # Section name contains embedded variables
            new_name = str(self.interpolate_parameter(name, ancestors, ancestors_names, name, global_config, []))
            value = self

        return new_name, value

    def interpolate(
        self, global_config: Optional[ConfigDict] = None, ancestors: Ancestors = (), ancestors_names: AncestorNames = ()
    ) -> 'Section':
        """Perform variable interpolation on the entire section.

        Recursively interpolates all parameters and section names,
        resolving variable references.

        Args:
            global_config: Global configuration for variable lookup
            ancestors: Tuple of ancestor sections
            ancestors_names: Tuple of ancestor section names

        Returns:
            This section (for method chaining)
        """
        global_config = global_config or {}

        # Interpolate all parameters in this section
        for name, parameter in list(self.items()):
            self[name] = self.interpolate_parameter(parameter, ancestors, ancestors_names, name, global_config, [])

        # Interpolate nested sections
        sections = {}
        for name, section in self.sections.items():
            if not name.startswith('_'):  # Don't interpolate special sections (like __many__)
                new_ancestors = ancestors + (self,)
                new_ancestors_names = ancestors_names + (name,)

                # Interpolate section name and get resolved section
                name, value = section.interpolate_section(name, new_ancestors, new_ancestors_names, global_config, [])

                # Merge resolved section with original and interpolate recursively
                section = config_from_dict(value).merge(section)
                section = section.interpolate(global_config, new_ancestors, new_ancestors_names)

            sections[name] = section

        self.sections = sections
        return self

    # Validation Methods
    # ------------------

    def merge_defaults(
        self, spec: 'Section', validator: Optional[Validator] = None, ancestors: AncestorNames = ()
    ) -> 'Section':
        """Merge default values from a specification.

        Adds default values for any missing parameters defined in the
        specification.

        Args:
            spec: Specification section containing default values
            validator: Validator instance to use
            ancestors: Ancestor section names for error reporting

        Returns:
            This section (for method chaining)

        Raises:
            ParameterError: If a required parameter is missing
        """
        validator = validator or Validator()

        # Add defaults for missing parameters
        for k in set(spec) - set(self):
            if k != '___many___':  # Skip special validation keys
                default = validator.get_default_value(spec[k], ancestors, k)
                if default is NO_DEFAULT:
                    raise ParameterError('required', sections=ancestors, name=k)

                self[k] = default

        # Recursively merge defaults for nested sections
        for name, section in spec.sections.items():
            if name != '__many__':  # Skip special validation sections
                section = self.sections.get(name, Section()).merge_defaults(section, validator, ancestors + (name,))
                self.sections[name] = section

        # Handle __many__ specification for dynamic sections
        many_sections = spec.sections.get('__many__')
        if many_sections is not None:
            for name in set(self.sections) - set(spec.sections):
                self.sections[name].merge_defaults(many_sections, validator, ancestors + (name,))

        return self

    def validate(
        self, spec: 'Section', validator: Optional[Validator] = None, ancestors_names: AncestorNames = ()
    ) -> 'Section':
        """Validate the section against a specification.

        Validates all parameters and nested sections according to the
        specification rules.

        Args:
            spec: Specification section defining validation rules
            validator: Validator instance to use
            ancestors_names: Ancestor section names for error reporting

        Returns:
            This section (for method chaining)
        """
        validator = validator or Validator()

        section_keys = set(self)
        spec_keys = set(spec)

        # Validate parameters that exist in both spec and config
        for k in section_keys & spec_keys:
            self[k] = validator.validate(spec[k], self[k], ancestors_names, k)

        # Validate nested sections that exist in both spec and config
        for k in set(self.sections) & set(spec.sections):
            self.sections[k].validate(spec.sections[k], validator, ancestors_names + (k,))

        # Handle ___many___ specification for dynamic parameters
        many_parameters = spec.get('___many___')
        if many_parameters is not None:
            for k in section_keys - spec_keys:
                self[k] = validator.validate(many_parameters, self[k], ancestors_names, k)

        # Handle __many__ specification for dynamic sections
        many_sections = spec.sections.get('__many__')
        if many_sections is not None:
            for k in set(self.sections) - set(spec.sections):
                self.sections[k].validate(many_sections, validator, ancestors_names + (k,))

        return self


Config = Section

# Configuration Factory Functions
# ===============================


def config_from_dict(d: ConfigDict) -> Section:
    """Create a configuration section from a dictionary.

    Recursively converts nested dictionaries into Section instances,
    providing a convenient way to create configurations programmatically.

    Args:
        d: Dictionary to convert to a configuration section

    Returns:
        A Section instance populated with the dictionary data

    Example:
        config = config_from_dict({
            'app_name': 'MyApp',
            'database': {
                'host': 'localhost',
                'port': 5432
            }
        })
        print(config['app_name'])  # 'MyApp'
        print(config['database']['host'])  # 'localhost'
    """
    return Config().from_dict(d)


def config_from_iter(lines: LineIterator, global_config: Optional[ConfigDict] = None, max_depth: int = 0) -> Section:
    """Create a configuration section from an iterator of lines.

    This is the core parsing function that processes configuration file
    syntax line by line. It's used internally by other factory functions.

    Args:
        lines: Iterator yielding configuration file lines
        global_config: Global configuration dictionary for interpolation
        max_depth: Maximum section nesting depth (0 = unlimited)

    Returns:
        A Section instance populated with the parsed configuration

    Raises:
        ParseError: If any line cannot be parsed
        SectionError: If section structure is invalid
        DirectiveError: If an unsupported directive is encountered
        ParameterError: If parameter names are duplicated

    Example:
        lines = iter([
            'app_name = MyApp',
            '[database]',
            'host = localhost'
        ])
        config = config_from_iter(lines)
    """
    return Config().from_iter(lines, global_config, max_depth)


def config_from_file(
    filename: str, global_config: Optional[ConfigDict] = None, max_depth: int = 0, encoding: str = 'utf-8'
) -> Section:
    """Create a configuration section from a file.

    Reads and parses a configuration file, handling encoding and
    file operations automatically.

    Args:
        filename: Path to the configuration file to read
        global_config: Global configuration dictionary for interpolation
        max_depth: Maximum section nesting depth (0 = unlimited)
        encoding: File encoding

    Returns:
        A Section instance populated with the file's configuration

    Raises:
        FileNotFoundError: If the configuration file doesn't exist
        PermissionError: If the file cannot be read
        ParseError: If the file contains invalid syntax
        SectionError: If section structure is invalid

    Example:
        config = config_from_file('app.cfg')
        print(config['app_name'])
    """
    with open(filename, encoding=encoding) as f:
        return config_from_iter(f, global_config, max_depth)


def config_from_string(string: str, global_config: Optional[ConfigDict] = None, max_depth: int = 0) -> Section:
    """Create a configuration section from a string.

    Parses configuration syntax from a string, useful for testing
    or when configuration comes from sources other than files.

    Args:
        string: Configuration content as a string
        global_config: Global configuration dictionary for interpolation
        max_depth: Maximum section nesting depth (0 = unlimited)

    Returns:
        A Section instance populated with the parsed configuration

    Raises:
        ParseError: If the string contains invalid syntax
        SectionError: If section structure is invalid

    Example:
        config_text = '''
        app_name = MyApp
        debug = true

        [database]
        host = localhost
        port = 5432
        '''
        config = config_from_string(config_text)
        print(config['app_name'])  # 'MyApp'
        print(config['database']['port'])  # '5432'
    """
    return config_from_iter(iter(string.splitlines()), global_config, max_depth)
