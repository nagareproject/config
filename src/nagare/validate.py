# Encoding: utf-8

# --
# Copyright (c) 2008-2025 Net-ng.
# All rights reserved.
#
# This software is licensed under the BSD License, as described in
# the file LICENSE.txt, which you should have received as part of
# this distribution.
# --

"""Configuration Validation Module.

This module provides a convertion and validation system for configuration files.
It includes convertion from strings to common data types (integers, floats, booleans, strings, lists)
and supports validation rules with constraints like min/max values, allowed options,
and default values.

The Validator class uses a functional approach with partial application to create
reusable validation functions that can be applied to configuration values.

Example:
    from nagare.validate import Validator

    validator = Validator()

    # Create a convertion and validation function for integer
    port_validator = validator.integer(min=1024, max=65535, default=8080)

    # Validate values
    port = port_validator('1234')  # Returns 1234
    port = port_validator(None)  # Returns 8080
    port = port_validator('10')  # Raises ParameterError: Error for parameter: the value '10' is too small
"""

from typing import Any, List, Tuple, TypeVar, Callable, Optional, overload
from functools import partial

from .config_exceptions import ParameterError, SpecificationError

# Type variables for generic validation functions
T = TypeVar('T')
NumberType = int | float

# Type aliases for cleaner annotations
Float = float
AncestorNames = tuple[str, ...]
ValidationFunction = Callable[[str, AncestorNames, str], Any]
ConverterFunction = Callable[[str], T]

# Sentinel object to distinguish between ``None`` as a default value and no default provided
NO_DEFAULT = object()


class Validator:
    """Validation system for configuration values.

    This class provides methods to convert and validate configuration values
    according to specifications. It supports type validation, range checking,
    default values, and complex data structures like lists and tuples.

    The validator uses a functional programming approach where validation
    methods return partial functions that can be applied to actual values.
    This allows for flexible composition of validation rules.
    """

    def __getitem__(self, name: str) -> Any:
        """Enable dictionary-style access to validator methods and special values.

        This method allows the validator to be used in ``eval()`` contexts
        where configuration specifications are evaluated as Python expressions.
        It provides access to validator methods and special boolean constants.

        Args:
            name: The name of the attribute/method to access

        Returns:
            The requested method, attribute, or constant value

        Raises:
            AttributeError: If the name starts with '_' (private attributes)

        Example:
            validator = Validator()
            validator['integer']  # Returns the integer method
            validator['True']     # Returns True
            validator['False']    # Returns False
        """
        # Prevent access to private attributes
        if name.startswith('_'):
            raise AttributeError(name)

        # Handle special boolean constants used in configuration specs
        if name == 'True':
            return True

        if name == 'False':
            return False

        # Return the requested method or attribute, fallback to the name itself
        return getattr(self, name, name)

    @staticmethod
    def _number(
        convert: Callable[[str], NumberType],
        min_val: Optional[NumberType],
        max_val: Optional[NumberType],
        default: NumberType | object,
        v: str | None,
        ancestors_names: AncestorNames = (),
        name: str = '',
    ) -> NumberType:
        """Internal method for validating numeric values (integers and floats).

        This is a helper method used by both ``integer()`` and ``float()`` validators.
        It handles type conversion, range validation, and default value assignment.

        Args:
            convert: Function to convert the value (int or float)
            min_val: Minimum allowed value
            max_val: Maximum allowed value
            default: Default value if v is None
            v: The value to validate
            ancestors_names: List of parent section names in the configuration file, for error reporting
            name: The parameter name in the configuration file, for error reporting

        Returns:
            The converted and validated numeric value

        Raises:
            ParameterError: If the value is invalid, out of range, or not a number
        """
        # Return default if no value provided
        if v is None:
            return default  # type: ignore

        # Lists are not valid numeric values
        if isinstance(v, list):
            raise ParameterError('not a number {}'.format(repr(v)), sections=ancestors_names, name=name)

        # Attempt to convert the value to the target numeric type
        try:
            value: NumberType = convert(v)
        except ValueError:
            raise ParameterError('not a number {}'.format(repr(v)), sections=ancestors_names, name=name)

        # Validate minimum value constraint
        if (min_val is not None) and (value < min_val):
            raise ParameterError("the value '{}' is too small".format(v), sections=ancestors_names, name=name)

        # Validate maximum value constraint
        if (max_val is not None) and (value > max_val):
            raise ParameterError("the value '{}' is too big".format(v), sections=ancestors_names, name=name)

        return value

    @classmethod
    def integer(
        cls,
        min: Optional[int] = None,
        max: Optional[int] = None,
        default: int | object = NO_DEFAULT,
        help: Optional[str] = None,
    ) -> ValidationFunction:
        """Create a validator for integer values.

        Returns a validation function that converts values to integers
        and optionally validates them against min/max constraints.

        Args:
            min: Minimum allowed value
            max: Maximum allowed value
            default: Default value if ``None`` is provided (``NO_DEFAULT`` means required)
            help: Help text for documentation (not used in validation)

        Returns:
            A validation function that takes (value, ancestors_names, name)

        Example:
            port_validator = Validator.integer(min=1024, max=65535, default=8080)
            port = port_validator('1234')  # Returns 1234
            port = port_validator(None)  # Returns 8080
        """
        return partial(cls._number, int, min, max, default)

    @classmethod
    @overload
    def float(cls, value: float) -> float: ...

    @classmethod
    @overload
    def float(
        cls, *, min: Optional[Float] = None, max: Optional[Float] = None, default: Float | object = NO_DEFAULT
    ) -> ValidationFunction: ...

    @classmethod
    def float(cls, *args: Any, **params: Any) -> Float | ValidationFunction:
        """Create a validator for floating-point values.

        This method can be used in two ways:
        1. As a validator factory: ``float(min=0.0, max=1.0, default=0.5)``
        2. As a direct constructor: ``float(3.14)``

        Args:
            *args: Values to construct a float directly
            **params: Validation parameters (``min``, ``max``, ``default``)

        Returns:
            Either a float value or a validation function

        Example:
            # As validator factory
            ratio_validator = Validator.float(min=0.0, max=1.0, default=0.5)
            ratio = ratio_validator('0.75')  # Returns 0.75

            # As direct constructor
            pi = Validator.float('3.14159')  # Returns 3.14159
        """
        min_val = params.get('min')
        max_val = params.get('max')
        default = params.get('default', NO_DEFAULT)

        # If args provided or no validation parameters, act as float constructor
        return (
            float(*args) if (args or default is NO_DEFAULT) else partial(cls._number, float, min_val, max_val, default)
        )

    @staticmethod
    def _to_boolean(v: str) -> bool:
        """Convert a string value to a boolean.

        Recognizes common boolean representations in configuration files.
        The conversion is case-insensitive.

        Args:
            v: String value to convert

        Returns:
            The converted boolean value

        Raises:
            ValueError: If the value cannot be converted to a boolean

        Supported true values (case insensitive): 'true', 'on', 'yes', '1'
        Supported false values (case insensitive): 'false', 'off', 'no', '0'
        """
        v = v.strip().lower()

        if v in ('true', 'on', 'yes', '1'):
            return True

        if v in ('false', 'off', 'no', '0'):
            return False

        raise ValueError('not a boolean {}'.format(repr(v)))

    @classmethod
    def _boolean(
        cls, default: bool | object, v: str | None, ancestors_names: AncestorNames = (), name: str = ''
    ) -> bool:
        """Internal method for validating boolean values.

        Args:
            default: Default value if v is None
            v: The value to validate
            ancestors_names: List of parent section names for error reporting
            name: The parameter name for error reporting

        Returns:
            The validated boolean value

        Raises:
            ParameterError: If the value cannot be converted to a boolean

        Supported true values (case insensitive): 'true', 'on', 'yes', '1'
        Supported false values (case insensitive): 'false', 'off', 'no', '0'
        """
        error = ParameterError('not a boolean {}'.format(repr(v)), sections=ancestors_names, name=name)

        # Return default if no value provided
        if v is None:
            return default  # type: ignore

        # Pass through actual boolean values
        if isinstance(v, bool):
            return v

        # Lists are not valid boolean values
        if isinstance(v, list):
            raise error

        # Attempt string-to-boolean conversion
        try:
            return cls._to_boolean(v)
        except ValueError:
            raise error

    @classmethod
    def boolean(cls, default: bool | object = NO_DEFAULT, help: Optional[str] = None) -> ValidationFunction:
        """Create a validator for boolean values.

        Returns a validation function that converts various representations
        to boolean values.

        Args:
            default: Default value if None is provided (NO_DEFAULT means required)
            help: Help text for documentation (not used in validation)

        Returns:
            A validation function that takes (value, ancestors_names, name)

        Example:
            debug_validator = Validator.boolean(default=False)

            debug = debug_validator('true')   # Returns True
            debug = debug_validator('off')    # Returns False
            debug = debug_validator(None)     # Returns False (default)

        Supported true values (case insensitive): 'true', 'on', 'yes', '1'
        Supported false values (case insensitive): 'false', 'off', 'no', '0'
        """
        return partial(cls._boolean, default)

    @staticmethod
    def _string(default: str | object, v: str | None, ancestors_names: AncestorNames = (), name: str = '') -> str:
        """Internal method for validating string values.

        Simply ensures the value is not a list and returns it as-is,
        or returns the default if the value is None.

        Args:
            default: Default value if v is None
            v: The value to validate
            ancestors_names: List of parent section names for error reporting
            name: The parameter name for error reporting

        Returns:
            The validated string value

        Raises:
            ParameterError: If the value is a list (not a valid string)
        """
        # Return default if no value provided
        if v is None:
            return default  # type: ignore

        # Lists are not valid string values
        if isinstance(v, list):
            raise ParameterError('not a string {}'.format(repr(v)), sections=ancestors_names, name=name)

        return str(v)

    @classmethod
    def string(cls, default: str | object = NO_DEFAULT, help: Optional[str] = None) -> ValidationFunction:
        """Create a validator for string values.

        Returns a validation function that validates string values
        and rejects lists.

        Args:
            default: Default value if None is provided (NO_DEFAULT means required)
            help: Help text for documentation (not used in validation)

        Returns:
            A validation function that takes (value, ancestors_names, name)

        Example:
            name_validator = Validator.string(default='Unnamed')

            name = name_validator('MyApp')  # Returns 'MyApp'
            name = name_validator(None)     # Returns 'Unnamed' (default)
        """
        return partial(cls._string, default)

    @staticmethod
    def _list(
        convert: ConverterFunction[T],
        min_val: Optional[int],
        max_val: Optional[int],
        default: List[T] | object,
        v: str | list | tuple | None,
        ancestors_names: AncestorNames = (),
        name: str = '',
    ) -> List[T]:
        """Internal method for validating list values.

        Handles list validation including element conversion, length validation,
        and automatic splitting of comma-separated strings into lists.

        Args:
            convert: Function to convert each list element
            min_val: Minimum number of elements allowed
            max_val: Maximum number of elements allowed
            default: Default value if v is None
            v: The value to validate
            ancestors_names: List of parent section names for error reporting
            name: The parameter name for error reporting

        Returns:
            The validated list with converted elements

        Raises:
            ParameterError: If validation fails (wrong length, conversion errors)
        """
        # Return default if no value provided
        if v is None:
            return default  # type: ignore

        # Convert comma-separated strings to lists
        if not isinstance(v, (list, tuple)):
            v = v.split(',')

        # Validate minimum length constraint
        if (min_val is not None) and (len(v) < min_val):
            raise ParameterError('not enough elements {}'.format(v), sections=ancestors_names, name=name)

        # Validate maximum length constraint
        if (max_val is not None) and (len(v) > max_val):
            raise ParameterError('too many elements {}'.format(v), sections=ancestors_names, name=name)

        # Convert each element using the provided converter function
        try:
            return [convert(e) for e in v]
        except ValueError:
            raise ParameterError('invalid value(s) in {}'.format(v), sections=ancestors_names, name=name)

    @classmethod
    @overload
    def list(cls, items: List[Any]) -> List[Any]: ...

    @classmethod
    @overload
    def list(
        cls,
        *,
        min: Optional[int] = None,
        max: Optional[int] = None,
        default: List[str] | object = NO_DEFAULT,
        help: Optional[str] = None,
    ) -> ValidationFunction: ...

    @classmethod
    def list(cls, *args: Any, **params: Any) -> List[Any] | ValidationFunction:
        """Create a validator for list values or construct a list directly.

        This method can be used in two ways:
        1. As a validator factory: list(min=1, max=10, default=[])
        2. As a direct constructor: list([1, 2, 3])

        Args:
            *args: Values to construct a list directly
            **params: Validation parameters (min, max, default, help)

        Returns:
            Either a list value or a validation function

        Example:
            # As validator factory
            tags_validator = Validator.list(min=1, max=5, default=[])
            tags = tags_validator('tag1,tag2,tag3')  # Returns ['tag1', 'tag2', 'tag3']

            # As direct constructor
            items = Validator.list(1, 2, 3)  # Returns [1, 2, 3]
        """
        min_val = params.get('min')
        max_val = params.get('max')
        default = params.get('default', NO_DEFAULT)
        help = params.get('help')

        # Determine if this should act as a list constructor or validator factory
        list_constructor = args or (min_val, max_val, default, help) == (None, None, NO_DEFAULT, None)
        return list(args) if list_constructor else partial(cls._list, str, min_val, max_val, default)

    @classmethod
    def string_list(
        cls,
        min: Optional[int] = None,
        max: Optional[int] = None,
        default: List[str] | object = NO_DEFAULT,
        help: Optional[str] = None,
    ) -> ValidationFunction:
        """Create a validator for lists of strings.

        This is a convenience method that creates a list validator
        specifically for string elements.

        Args:
            min: Minimum number of elements
            max: Maximum number of elements
            default: Default value if None is provided
            help: Help text for documentation

        Returns:
            A validation function for string lists

        Example:
            tags_validator = Validator.string_list(min=1, default=['default'])
            tags = tags_validator('web,api,mobile')  # Returns ['web', 'api', 'mobile']
        """
        return partial(cls._list, str, min, max, default)

    # Alias for backward compatibility
    force_list = string_list

    @classmethod
    def _tuple(
        cls,
        min_val: Optional[int],
        max_val: Optional[int],
        default: Tuple[str, ...] | object,
        v: str | None,
        ancestors_names: AncestorNames = (),
        name: str = '',
    ) -> Tuple[str, ...]:
        """Internal method for validating tuple values.

        Uses the list validation logic then converts the result to a tuple.

        Args:
            min_val: Minimum number of elements
            max_val: Maximum number of elements
            default: Default value if v is None
            v: The value to validate
            ancestors_names: List of parent section names for error reporting
            name: The parameter name for error reporting

        Returns:
            The validated tuple with string elements
        """
        return tuple(cls._list(str, min_val, max_val, default, v, ancestors_names, name))

    @classmethod
    @overload
    def tuple(cls, items: Tuple[Any, ...]) -> Tuple[Any, ...]: ...

    @classmethod
    @overload
    def tuple(
        cls,
        *,
        min: Optional[int] = None,
        max: Optional[int] = None,
        default: Tuple[str, ...] | object = NO_DEFAULT,
        help: Optional[str] = None,
    ) -> ValidationFunction: ...

    @classmethod
    def tuple(cls, *args: Any, **params: Any) -> Tuple[Any, ...] | ValidationFunction:
        """Create a validator for tuple values or construct a tuple directly.

        This method can be used in two ways:
        1. As a validator factory: tuple(min=2, max=3, default=())
        2. As a direct constructor: tuple((1, 2, 3))

        Args:
            *args: Values to construct a tuple directly
            **params: Validation parameters (min, max, default, help)

        Returns:
            Either a tuple value or a validation function

        Example:
            # As validator factory
            coord_validator = Validator.tuple(min=2, max=2, default=(0, 0))
            coord = coord_validator('10,20', [], 'position')  # Returns ('10', '20')

            # As direct constructor
            point = Validator.tuple((1, 2, 3))  # Returns (1, 2, 3)
        """
        min_val = params.get('min')
        max_val = params.get('max')
        default = params.get('default', NO_DEFAULT)
        help = params.get('help')

        # Determine if this should act as a tuple constructor or validator factory
        tuple_constructor = args or (min_val, max_val, default, help) == (None, None, NO_DEFAULT, None)
        return args if tuple_constructor else partial(cls._tuple, min_val, max_val, default)

    @classmethod
    def int_list(
        cls,
        min: Optional[int] = None,
        max: Optional[int] = None,
        default: List[int] | object = NO_DEFAULT,
        help: Optional[str] = None,
    ) -> ValidationFunction:
        """Create a validator for lists of integers.

        This is a convenience method that creates a list validator
        specifically for integer elements.

        Args:
            min: Minimum number of elements
            max: Maximum number of elements
            default: Default value if None is provided
            help: Help text for documentation

        Returns:
            A validation function for integer lists

        Example:
            ports_validator = Validator.int_list(min=1, max=10, default=[8080])
            ports = ports_validator('80,443,8080')  # Returns [80, 443, 8080]
        """
        return partial(cls._list, int, min, max, default)

    @classmethod
    def float_list(
        cls,
        min: Optional[int] = None,
        max: Optional[int] = None,
        default: List[Float] | object = NO_DEFAULT,
        help: Optional[str] = None,
    ) -> ValidationFunction:
        """Create a validator for lists of floating-point numbers.

        This is a convenience method that creates a list validator
        specifically for float elements.

        Args:
            min: Minimum number of elements
            max: Maximum number of elements
            default: Default value if None is provided
            help: Help text for documentation

        Returns:
            A validation function for float lists

        Example:
            ratios_validator = Validator.float_list(min=2, default=[0.5, 1.0])
            ratios = ratios_validator('0.25,0.75,1.0')  # Returns [0.25, 0.75, 1.0]
        """
        return partial(cls._list, float, min, max, default)

    @classmethod
    def bool_list(
        cls,
        min: Optional[int] = None,
        max: Optional[int] = None,
        default: List[bool] | object = NO_DEFAULT,
        help: Optional[str] = None,
    ) -> ValidationFunction:
        """Create a validator for lists of boolean values.

        This is a convenience method that creates a list validator
        specifically for boolean elements.

        Args:
            min: Minimum number of elements
            max: Maximum number of elements
            default: Default value if None is provided
            help: Help text for documentation

        Returns:
            A validation function for boolean lists

        Example:
            flags_validator = Validator.bool_list(min=2, default=[False, True])
            flags = flags_validator('true,false,on')  # Returns [True, False, True]
        """
        return partial(cls._list, cls._to_boolean, min, max, default)

    @staticmethod
    def _option(
        options: Tuple[Any, ...], default: Any | object, v: str, ancestors_names: AncestorNames = (), name: str = ''
    ) -> Any:
        """Internal method for validating option values.

        Ensures the value is one of the allowed options.

        Args:
            options: Tuple of allowed values
            default: Default value if v is None
            v: The value to validate
            ancestors_names: List of parent section names for error reporting
            name: The parameter name for error reporting

        Returns:
            The validated option value

        Raises:
            ParameterError: If the value is not in the allowed options
        """
        # Return default if no value provided
        if v is None:
            return default

        # Check if value is in allowed options
        if v not in options:
            raise ParameterError('not a valid option {}'.format(repr(v)), sections=ancestors_names, name=name)

        return v

    @classmethod
    def option(cls, *args: Any, **params: Any) -> ValidationFunction:
        """Create a validator for option values (enum-like behavior).

        Restricts values to a predefined set of allowed options.

        Args:
            *args: The allowed option values
            **params: Additional parameters (default)

        Returns:
            A validation function for option values

        Example:
            level_validator = Validator.option('DEBUG', 'INFO', 'WARNING', 'ERROR', default='INFO')
            level = level_validator('DEBUG')  # Returns 'DEBUG'
            level = level_validator('INVALID')  # Raises ParameterError
        """
        default = params.get('default', NO_DEFAULT)

        return partial(cls._option, args, default)

    def validate(self, expr: str, v: str | None, ancestors_name: AncestorNames = (), name: str = '') -> Any:
        """Validate a value against a specification expression.

        This method evaluates a specification expression (like "integer(min=1, max=100)")
        and applies the resulting validator to the provided value.

        Args:
            expr: The specification expression to evaluate
            v: The value to convert and validate
            ancestors_name: List of parent section names for error reporting
            name: The parameter name for error reporting

        Returns:
            The converted and validated value

        Raises:
            SpecificationError: If the specification expression is invalid
            ParameterError: If the value fails validation

        Example:
            validator = Validator()
            result = validator.validate('integer(min=1, max=100)', '50')
            # Returns 50 (converted to int)
        """
        try:
            # Evaluate the specification expression in a controlled environment
            # The validator instance is provided as the global context
            validation = eval(expr, {}, self)  # type: ignore # noqa: S307

            # If the result is not a partial function, call it to get the validator
            if not isinstance(validation, partial):
                validation = validation()

            # Apply the validator to the value
            return validation(v, ancestors_name, name)
        except Exception:
            # Create a clean error without the original traceback
            e = SpecificationError('invalid specification {}'.format(repr(expr)), sections=ancestors_name, name=name)
            e.__cause__ = None

            raise e

    def get_default_value(self, expr: str, ancestors_names: AncestorNames = (), name: str = '') -> Any:
        """Extract the default value from a specification expression.

        This method evaluates a specification and returns its default value
        by passing None as the value to validate.

        Args:
            expr: The specification expression to evaluate
            ancestors_names: List of parent section names for error reporting
            name: The parameter name for error reporting

        Returns:
            The default value defined in the specification

        Example:
            validator = Validator()
            default = validator.get_default_value('integer(min=1, default=8080)')  # Returns 8080
        """
        return self.validate(expr, None, ancestors_names, name)
