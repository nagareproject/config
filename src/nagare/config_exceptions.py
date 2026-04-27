# --
# Copyright (c) 2014-2026 Net-ng.
# All rights reserved.
#
# This software is licensed under the BSD License, as described in
# the file LICENSE.txt, which you should have received as part of
# this distribution.
# --

"""Configuration Exception Classes Module.

This module defines the hierarchy of exceptions used throughout the nagare
configuration system. It provides detailed error reporting with context
information including line numbers, section paths, and parameter names.

The exception hierarchy is designed to provide granular error handling while
maintaining clear error messages for debugging configuration issues.

Example:
    try:
        config = config_from_file('invalid.cfg')
    except ParseError as e:
        print(f"Parse error at line {e.line}: {e.error}")
    except SectionError as e:
        print(f"Section error in {e.sections}: {e.error}")
"""


class ConfigError(ValueError):
    """Base exception class for all configuration-related errors.

    This is the root exception in the configuration error hierarchy. It provides
    basic error reporting functionality with optional line number tracking.
    All other configuration exceptions inherit from this class.

    Args:
        error: The error message describing what went wrong
        line: Optional line number where the error occurred

    Example:
        >>> try:
        ...     raise ConfigError("Something went wrong", line=42)
        ... except ConfigError as e:
        ...     print(e)  # "Error line #42: Something went wrong"
    """

    def __init__(self, error: str, line: int | None = None) -> None:
        """Initialize a ConfigError instance.

        Args:
            error: The error message describing the problem
            line: Optional line number where the error occurred
        """
        super().__init__(error)
        self.error = error
        self.line = line

    @property
    def context(self) -> str:
        """Get contextual information about where the error occurred.

        Returns:
            A string containing line number information if available,
            empty string otherwise

        Example:
            >>> error = ConfigError("test", line=42)
            >>> error.context
            ' line #42'
        """
        return f' line #{self.line}' if self.line else ''

    def __str__(self) -> str:
        """Return a human-readable string representation of the error.

        Returns:
            A formatted error message including context information

        Example:
            >>> str(ConfigError("Invalid syntax", line=10))
            'Error line #10: Invalid syntax'
        """
        return f'Error{self.context}: {self.error}'


class ParseError(ConfigError):
    """Exception raised when configuration file parsing fails.

    This exception is raised when the parser encounters invalid syntax
    in a configuration file that cannot be processed according to the
    expected format rules.

    Inherits all functionality from ConfigError and adds no additional
    behavior, serving primarily as a more specific exception type for
    parsing-related errors.

    Example:
        >>> raise ParseError("Invalid line format", line=15)
        ParseError: Error line #15: Invalid line format
    """


class ContextualParseError(ParseError):
    """Base class for parse errors that include hierarchical context information.

    This exception extends ParseError to include information about the section
    hierarchy and parameter context where the error occurred. It serves as the
    base class for more specific contextual errors.

    Args:
        error: The error message describing what went wrong
        line: Optional line number where the error occurred
        sections: Tuple of section names representing the hierarchy path
        name: Optional parameter or section name where the error occurred

    Attributes:
        error (str): The error message
        line (int | None): Line number where the error occurred
        name (str | None): Name of the parameter/section where error occurred

    Example:
        >>> error = ContextualParseError(
        ...     "Invalid value",
        ...     line=20,
        ...     sections=("database", "connection"),
        ...     name="timeout"
        ... )
        >>> error.sections
        ' [database] > [[connection]] > timeout'
    """

    def __init__(
        self, error: str, line: int | None = None, sections: tuple[str, ...] = (), name: str | None = None
    ) -> None:
        """Initialize a ContextualParseError instance.

        Args:
            error: The error message describing the problem
            line: Optional line number where the error occurred
            sections: Tuple of section names forming the hierarchy path
            name: Optional parameter or section name where the error occurred
        """
        super().__init__(error, line)
        self._sections = sections
        self.name = name

    @property
    def sections(self) -> str:
        """Get a formatted representation of the section hierarchy.

        Creates a human-readable path showing the nested section structure
        where the error occurred, with proper bracket notation indicating
        nesting levels.

        Returns:
            A formatted string showing the section path, or empty string
            if no sections are specified

        Example:
            >>> error = ContextualParseError(
            ...     "test",
            ...     sections=("app", "database", "pool"),
            ...     name="size"
            ... )
            >>> error.sections
            ' [app] > [[database]] > [[[pool]]] > size'
        """
        # Format each section with appropriate bracket nesting level
        sections = [('[' * level) + section + (']' * level) for level, section in enumerate(self._sections, 1)]

        # Add the parameter/section name if specified
        if self.name:
            sections.append(self.name)

        # Return formatted path with separators, or empty string if no sections
        return (' ' + (' > '.join(sections))) if sections else ''


class SpecificationError(ContextualParseError):
    """Exception raised when configuration specification validation fails.

    This exception is thrown when a configuration specification contains
    invalid validation rules or when the specification itself cannot be
    processed correctly.

    Inherits contextual information from ContextualParseError and adds
    specification-specific context formatting.

    Example:
        >>> error = SpecificationError(
        ...     "Invalid validator",
        ...     line=5,
        ...     sections=("app",),
        ...     name="port"
        ... )
        >>> str(error)
        'Error line #5 for specification [app] > port: Invalid validator'
    """

    @property
    def context(self) -> str:
        """Get specification-specific context information.

        Returns:
            A formatted string indicating this is a specification error
            with the full hierarchical context
        """
        return super().context + f' for specification{self.sections}'


class SectionError(ContextualParseError):
    """Exception raised when section definition or structure is invalid.

    This exception is thrown when there are problems with section definitions,
    such as invalid nesting, duplicate section names, or malformed section
    headers in the configuration file.

    Example:
        >>> error = SectionError(
        ...     "Duplicate section name",
        ...     line=10,
        ...     sections=("app",),
        ...     name="database"
        ... )
        >>> str(error)
        'Error line #10 for section [app] > database: Duplicate section name'
    """

    @property
    def context(self) -> str:
        """Get section-specific context information.

        Returns:
            A formatted string indicating this is a section error
            with the full hierarchical context
        """
        return super().context + f' for section{self.sections}'


class ParameterError(SpecificationError):
    """Exception raised when parameter validation or definition fails.

    This exception is thrown when there are issues with parameter definitions,
    validation failures, missing required parameters, or invalid parameter
    values according to their specifications.

    Note that ParameterError inherits from SpecificationError rather than
    ContextualParseError directly, as parameter errors are typically related
    to specification validation.

    Example:
        >>> error = ParameterError(
        ...     "Value out of range",
        ...     line=15,
        ...     sections=("database",),
        ...     name="port"
        ... )
        >>> str(error)
        'Error line #15 for specification [database] > port: Value out of range'
    """

    @property
    def context(self) -> str:
        """Get parameter-specific context information.

        Returns:
            A formatted string indicating this is a parameter error
            with the full hierarchical context, including both
            specification context (from parent class) and parameter context
        """
        return super().context + f' for parameter{self.sections}'


class InterpolationError(ContextualParseError):
    """Exception raised when variable interpolation fails.

    This exception is thrown when there are problems during variable
    interpolation, such as undefined variables, circular references,
    or invalid interpolation syntax.

    Example:
        >>> error = InterpolationError(
        ...     "Circular reference detected",
        ...     sections=("app", "logging"),
        ...     name="file_path"
        ... )
        >>> str(error)
        'Error in section [app] > [[logging]] > file_path: Circular reference detected'
    """

    @property
    def context(self) -> str:
        """Get interpolation-specific context information.

        Returns:
            A formatted string indicating this is an interpolation error
            with the full hierarchical context
        """
        return super().context + f' in section{self.sections}'


class DirectiveError(ContextualParseError):
    r"""Exception raised when configuration directives are invalid or unsupported.

    This exception is thrown when the parser encounters configuration directives
    (special processing instructions) that are either malformed or not supported
    by the current implementation.

    Example:
        >>> error = DirectiveError(
        ...     "Unsupported directive 'include'",
        ...     line=8,
        ...     sections=("app",),
        ...     name="config"
        ... )
        >>> str(error)
        'Error line #8 in section [app] > config: Unsupported directive \'include\''
    """

    @property
    def context(self) -> str:
        """Get directive-specific context information.

        Returns:
            A formatted string indicating this is a directive error
            with the full hierarchical context
        """
        return super().context + f' in section{self.sections}'
