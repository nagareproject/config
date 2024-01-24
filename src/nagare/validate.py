# Encoding: utf-8

# --
# Copyright (c) 2008-2024 Net-ng.
# All rights reserved.
#
# This software is licensed under the BSD License, as described in
# the file LICENSE.txt, which you should have received as part of
# this distribution.
# --

from functools import partial

from .config_exceptions import ParameterError, SpecificationError

NO_DEFAULT = object()


class Validator(object):
    def __getitem__(self, name):
        if name.startswith('_'):
            raise AttributeError(name)

        if name == 'True':
            return True

        if name == 'False':
            return False

        return getattr(self, name, name)

    @staticmethod
    def _number(convert, min, max, default, v, ancestors_names, name):
        if v is None:
            return default

        if isinstance(v, list):
            raise ParameterError('not a number {}'.format(repr(v)), sections=ancestors_names, name=name)

        try:
            v = convert(v)
        except ValueError:
            raise ParameterError('not a number {}'.format(repr(v)), sections=ancestors_names, name=name)

        if (min is not None) and (v < min):
            raise ParameterError("the value '{}' is too small".format(v), sections=ancestors_names, name=name)

        if (max is not None) and (v > max):
            raise ParameterError("the value '{}' is too big".format(v), sections=ancestors_names, name=name)

        return v

    @classmethod
    def integer(cls, min=None, max=None, default=NO_DEFAULT, help=None):
        return partial(cls._number, int, min, max, default)

    @classmethod
    def float(cls, *args, **params):
        min = params.get('min')
        max = params.get('min')
        default = params.get('default', NO_DEFAULT)

        return float(*args) if (args or default is NO_DEFAULT) else partial(cls._number, float, min, max, default)

    @staticmethod
    def _to_boolean(v):
        v = v.strip().lower()

        if v in ('true', 'on', 'yes', '1'):
            return True

        if v in ('false', 'off', 'no', '0'):
            return False

        raise ValueError('not a boolean {}'.format(repr(v)))

    @classmethod
    def _boolean(cls, default, v, ancestors_names, name):
        error = ParameterError('not a boolean {}'.format(repr(v)), sections=ancestors_names, name=name)

        if v is None:
            return default

        if isinstance(v, bool):
            return v

        if isinstance(v, list):
            raise error

        try:
            return cls._to_boolean(v)
        except ValueError:
            raise error

    @classmethod
    def boolean(cls, default=NO_DEFAULT, help=None):
        return partial(cls._boolean, default)

    @staticmethod
    def _string(default, v, ancestors_names, name):
        if v is None:
            return default

        if isinstance(v, list):
            raise ParameterError('not a string {}'.format(repr(v)), sections=ancestors_names, name=name)

        return v

    @classmethod
    def string(cls, default=NO_DEFAULT, help=None):
        return partial(cls._string, default)

    @staticmethod
    def _list(convert, min, max, default, v, ancestors_names, name):
        if v is None:
            return default

        if not isinstance(v, (list, tuple)):
            v = v.split(',')

        if (min is not None) and (len(v) < min):
            raise ParameterError('not enougth elements {}'.format(v), sections=ancestors_names, name=name)

        if (max is not None) and (len(v) > max):
            raise ParameterError('too many elements {}'.format(v), sections=ancestors_names, name=name)

        try:
            return [convert(e) for e in v]
        except ValueError:
            raise ParameterError('invalid value(s) in {}'.format(v), sections=ancestors_names, name=name)

    @classmethod
    def list(cls, *args, **params):
        min = params.get('min')
        max = params.get('min')
        default = params.get('default', NO_DEFAULT)
        help = params.get('help')

        list_constructor = args or (min, max, default, help) == (None, None, NO_DEFAULT, None)
        return list(args) if list_constructor else partial(cls._list, str, min, max, default)

    @classmethod
    def string_list(cls, min=None, max=None, default=NO_DEFAULT, help=None):
        return partial(cls._list, str, min, max, default)

    force_list = string_list

    @classmethod
    def _tuple(cls, min, max, default, v, ancestors_names, name):
        return tuple(cls._list(str, min, max, default, v, ancestors_names, name))

    @classmethod
    def tuple(cls, *args, **params):
        min = params.get('min')
        max = params.get('min')
        default = params.get('default', NO_DEFAULT)
        help = params.get('help')

        tuple_constructor = args or (min, max, default, help) == (None, None, NO_DEFAULT, None)
        return args if tuple_constructor else partial(cls._tuple, min, max, default)

    @classmethod
    def int_list(cls, min=None, max=None, default=NO_DEFAULT, help=None):
        return partial(cls._list, int, min, max, default)

    @classmethod
    def float_list(cls, min=None, max=None, default=NO_DEFAULT, help=None):
        return partial(cls._list, float, min, max, default)

    @classmethod
    def bool_list(cls, min=None, max=None, default=NO_DEFAULT, help=None):
        return partial(cls._list, cls._to_boolean, min, max, default)

    @staticmethod
    def _option(options, default, v, ancestors_names, name):
        if v is None:
            return default

        if v not in options:
            raise ParameterError('not a valid option {}'.format(repr(v)), sections=ancestors_names, name=name)

        return v

    @classmethod
    def option(cls, *args, **params):
        default = params.get('default', NO_DEFAULT)

        return partial(cls._option, args, default)

    def validate(self, expr, v, ancestors_name, name):
        try:
            validation = eval(expr, {}, self)  # noqa: S307
            if not isinstance(validation, partial):
                validation = validation()

            return validation(v, ancestors_name, name)
        except Exception:
            e = SpecificationError('invalid specification {}'.format(repr(expr)), sections=ancestors_name, name=name)
            e.__cause__ = None

            raise e

    def get_default_value(self, expr, ancestors_names, name):
        return self.validate(expr, None, ancestors_names, name)
