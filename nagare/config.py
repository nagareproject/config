# Encoding: utf-8

# --
# Copyright (c) 2008-2022 Net-ng.
# All rights reserved.
#
# This software is licensed under the BSD License, as described in
# the file LICENSE.txt, which you should have received as part of
# this distribution.
# --

import re

from .config_exceptions import (  # noqa: F401
    ConfigError,
    ParseError,
    SpecificationError,
    SectionError,
    ParameterError,
    InterpolationError,
    DirectiveError
)
from .validate import Validator, NO_DEFAULT

QUOTES = ('"', "'")

TAIL = re.compile(r'''
    \s*,\s*
    (
       (?P<tail1>"[^"]*")
       |
       (?P<tail2>'[^']*')
       |
       (?:[^"',\s]*)
    )
''', re.VERBOSE)

VALUE = re.compile(r'''
    (?P<value>
        (?P<head>("[^"]*")|('[^']*')|([^'"]*?))
        (?P<tail>{})*
    )
'''.format(TAIL.pattern), re.VERBOSE)

FULL_VALUE = re.compile('^{}$'.format(VALUE.pattern), re.VERBOSE)

LINE = re.compile(r'''^
    \s*
    (
        (\#.*)
        |
        (
            (?P<section_in>\[+)
            \s*
            (?P<section>
                ("[^"]+")|('[^']+')
                |
                (\$\((?P<section_directive>[^ ]+)(\ (?P<section_directive_args>[^)]+))?\))
                |
                ([^'"]+?)
            )
            \s*
            (?P<section_out>\]+)
            \s*
            (\#?.*)
        )
        |
        (
            (?P<name>("[^"]+")|('[^']+')|([^'"]+?))
            \s*=\s*
            (
                (
                    (?P<multi_delimiter_start>(\''')|("""))(?P<multi>.*?)(?P<multi_delimiter_end>(?P=multi_delimiter_start))?
                )|{}
            )
       )
       \s*(\#.*)?
    )?
    $
'''.format(VALUE.pattern), re.VERBOSE)

INTERPOLATION = re.compile(r'''
    \$
    (
        (?P<escaped>\$)
        |
        (?P<named>[_a-zA-Z0-9]+)
        |
        (
            {
                (?P<braced>[^:}]+)
                (:
                    (?P<default>
                        (
                            (\${[^}]+})
                            |
                            .
                        )*
                    )
                )?
            }
        )
    )
''', re.VERBOSE)

FULL_INTERPOLATION = re.compile('^{}$'.format(INTERPOLATION.pattern), re.VERBOSE)


class Section(dict):

    def __init__(self, *args, **kw):
        super(Section, self).__init__(*args, **kw)
        self.sections = {}

    def __bool__(self):
        return bool(super(Section, self)) or bool(self.sections)
    __nonzero__ = __bool__

    def __getitem__(self, k):
        return super(Section, self).__getitem__(k) if k in self else self.sections[k]

    def get(self, k, default=None):
        return self.__getitem__(k) if k in self else self.sections.get(k, default)

    def pop(self, k, default=None):
        return self.__getitem(k) if k in self else self.sections.pop(k, default)

    def setdefault(self, k, v):
        return (self.sections.setdefault if isinstance(v, dict) else self.setdefault)(k, v)

    def dict(self):
        return dict(self, **{k: v.dict() for k, v in self.sections.items()})

    def merge(self, config):
        self.update(config)

        for name, section in config.sections.items():
            self.sections[name] = self.sections.get(name, Section()).merge(section)

        return self

    def display(self, indent=0, level=0, filter_parameter=lambda parameter: True):
        spaces = ' ' * (indent * level)

        for k, v in sorted(self.items(), key=lambda param: (param[0] == '___many___', param[0])):
            if filter_parameter(k):
                print(spaces + k + ' = ' + repr(v))

        for k, v in sorted(self.sections.items(), key=lambda section: (section[0] == '__many__', section)):
            if filter_parameter(k):
                print('')
                print(spaces + ('[' * (level + 1)) + k + (']' * (level + 1)))
                v.display(indent, level + 1, filter_parameter)

    # Parsing
    # -------

    def from_dict(self, d):
        for k, v in d.items():
            if isinstance(v, dict):
                self.sections[k] = Section().from_dict(v)
            else:
                self[k] = v

        return self

    @staticmethod
    def strip_quotes(v):
        if v.startswith(QUOTES):
            v = v[1:]

        if v.endswith(QUOTES):
            v = v[:-1]

        return v

    @classmethod
    def _parse_value(cls, value, head, tail, tail1, tail2, **kw):
        if not tail:
            value = cls.strip_quotes(head)
        else:
            if head.startswith(('"', "'")) or tail1 or tail2:
                value = [cls.strip_quotes(e) for e, _, _ in TAIL.findall(',' + value)]

        return value

    @classmethod
    def parse_value(cls, value):
        return cls._parse_value(**FULL_VALUE.match(value).groupdict())

    @staticmethod
    def parse_multilines(lines, nb_lines, value, end):
        start_line = nb_lines
        line_pattern = re.compile(r'^(?P<value>.*?)(?P<delimiter>{}\s*(#.*)?)?$'.format(end))

        for line in lines:
            nb_lines += 1
            m = line_pattern.match(line[:-1])
            value += '\n' + m.group('value')
            if m.group('delimiter'):
                break
        else:
            raise ParseError('no multiline value end found', start_line)

        return nb_lines, value

    def from_iter(self, lines, global_config=None, max_depth=0, ancestors=(), ancestors_names=(), nb_lines=0):
        for line in lines:
            nb_lines += 1
            x = LINE.match(line.rstrip())
            if not x:
                raise ParseError("invalid line '{}'".format(line.strip()), nb_lines)

            m = x.groupdict()
            if m['section']:
                name = self.strip_quotes(m['section'])

                level = len(m['section_in'])
                if len(m['section_out']) != level:
                    raise SectionError('cannot compute the section depth', nb_lines, ancestors_names, name)

                if max_depth and (level >= max_depth):
                    return self

                if level == (len(ancestors) + 1):
                    parent = self
                    section_ancestors = ancestors
                    section_ancestors_names = ancestors_names
                elif level <= len(ancestors):
                    ancestors = ancestors[:level]
                    parent = ancestors[-1]
                    section_ancestors = ancestors[:-1]
                    section_ancestors_names = ancestors_names[:level - 1]
                else:
                    raise SectionError('section too nested', nb_lines, ancestors_names, name)

                directive = m.get('section_directive')
                if not directive:
                    if (name in parent) or (name in parent.sections):
                        raise SectionError('duplicate section name', nb_lines, section_ancestors_names, name)

                    parent.sections[name] = None
                    parent.sections[name] = Section().from_iter(
                        lines,
                        global_config,
                        max_depth,
                        section_ancestors + (parent,), section_ancestors_names + (name,),
                        nb_lines
                    )
                else:
                    raise DirectiveError('invalid directive', nb_lines, ancestors_names, directive)

            if m['name']:
                name = self.strip_quotes(m['name'])
                if (name in self) or (name in self.sections):
                    raise ParameterError('duplicate parameter name', nb_lines, ancestors_names, name)

                if m['multi_delimiter_start']:
                    if m['multi_delimiter_end']:
                        value = m['multi']
                    else:
                        nb_lines, value = self.parse_multilines(lines, nb_lines, m['multi'], m['multi_delimiter_start'])
                else:
                    value = self._parse_value(**m)

                self[name] = value

        return self

    # Interpolation
    # -------------

    def get_parameter(self, names):
        name = names.pop(0)
        if names:
            ancestors, section, value = [], None, self.sections.get(name)
            if value:
                ancestors, section, value = value.get_parameter(names)
                ancestors.insert(0, self)
        else:
            ancestors, section, value = [self], self, self.get(name)

        return ancestors, section, value

    def find_parameter(self, name, ancestors, global_config):
        section, value = self, self.get(name)
        if value is None:
            if ancestors:
                section, value = ancestors[-1].find_parameter(name, ancestors[:-1], global_config)
            else:
                section, value = None, global_config.get(name)

        return section, value

    def _interpolate(self, ancestors, ancestors_names, name, global_config, refs, escaped, named, braced, default):
        if escaped:
            return None, '$'

        parameter_name = named or braced
        if parameter_name.count('/') == 0:
            section, value = self.find_parameter(parameter_name, ancestors, global_config)
        else:
            if ancestors:
                parameter_name = parameter_name.strip('/')
                ancestors, section, value = ancestors[0].get_parameter(parameter_name.split('/'))
            else:
                value = None

        if (value is None) and (default is not None):
            value = self.parse_value(default)

        if value is None:
            raise InterpolationError(
                'variable {} not found'.format(repr(parameter_name)),
                sections=ancestors_names,
                name=name
            )

        ref = (id(section), parameter_name)
        if ref in refs:
            loop = [repr(r[1]) for r in refs]
            raise InterpolationError(
                'interpolation loop {} detected'.format(' -> '.join(loop)),
                sections=ancestors_names
            )

        value = self.interpolate_parameter(value, ancestors, ancestors_names, name, global_config, refs + [ref])

        if isinstance(value, list):
            raise InterpolationError(
                "variable {} is list {}".format(repr(parameter_name), repr(value)),
                sections=ancestors_names,
                name=name
            )

        return parameter_name, value

    def _interpolate_parameter(self, ancestors, ancestors_names, name, global_config, refs, **match):
        name, value = self._interpolate(ancestors, ancestors_names, name, global_config, refs, **match)
        if isinstance(value, list):
            raise InterpolationError(
                "variable {} is list {}".format(repr(name), repr(value)),
                sections=ancestors_names,
                name=name
            )

        return value

    def interpolate_parameter(self, value, ancestors, ancestors_names, name, global_config, refs):
        is_list = isinstance(value, list)

        def interpolate(match):
            return self._interpolate_parameter(ancestors, ancestors_names, name, global_config, refs, **match.groupdict())

        value = [
            INTERPOLATION.sub(interpolate, e) if isinstance(e, str) else e
            for e in (value if is_list else [value])
        ]

        return value if is_list else value[0]

    def interpolate_section(self, name, ancestors, ancestors_names, global_config, refs):
        match = FULL_INTERPOLATION.match(name)
        if match:
            new_name, value = self._interpolate(ancestors, ancestors_names, name, global_config, refs, **match.groupdict())
            if isinstance(value, Section):
                value.interpolate(global_config, ancestors, ancestors_names)
                new_name = new_name.split('/')[-1]
            else:
                new_name, value = value, config_from_dict({})
        else:
            new_name = self.interpolate_parameter(name, ancestors, ancestors_names, name, global_config, [])
            value = self

        return new_name, value

    def interpolate(self, global_config=None, ancestors=(), ancestors_names=()):
        global_config = global_config or {}

        for name, parameter in list(self.items()):
            self[name] = self.interpolate_parameter(parameter, ancestors, ancestors_names, name, global_config, [])

        sections = {}
        for name, section in self.sections.items():
            if not name.startswith('_'):
                new_ancestors = ancestors + (self,)
                new_ancestors_names = ancestors_names + (name,)

                name, value = section.interpolate_section(name, new_ancestors, new_ancestors_names, global_config, [])

                section = config_from_dict(value).merge(section)
                section = section.interpolate(global_config, new_ancestors, new_ancestors_names)

            sections[name] = section

        self.sections = sections

        return self

    # Validation
    # ----------

    def merge_defaults(self, spec, validator=None, ancestors=()):
        validator = validator or Validator()

        for k in set(spec) - set(self):
            if k != '___many___':
                default = validator.get_default_value(spec[k], ancestors, k)
                if default is NO_DEFAULT:
                    raise ParameterError('required', sections=ancestors, name=k)

                self[k] = default

        for name, section in spec.sections.items():
            if name != '__many__':
                section = self.sections.get(name, Section()).merge_defaults(section, validator, ancestors + (name,))
                self.sections[name] = section

        many_sections = spec.sections.get('__many__')
        if many_sections is not None:
            for name in (set(self.sections) - set(spec.sections)):
                self.sections[name].merge_defaults(many_sections, validator, ancestors + (name,))

        return self

    def validate(self, spec, validator=None, ancestors_names=()):
        validator = validator or Validator()

        section_keys = set(self)
        spec_keys = set(spec)

        for k in (section_keys & spec_keys):
            self[k] = validator.validate(spec[k], self[k], ancestors_names, k)

        for k in (set(self.sections) & set(spec.sections)):
            self.sections[k].validate(spec.sections[k], validator, ancestors_names + (k,))

        many_parameters = spec.get('___many___')
        if many_parameters is not None:
            for k in section_keys - spec_keys:
                self[k] = validator.validate(many_parameters, self[k], ancestors_names, k)

        many_sections = spec.sections.get('__many__')
        if many_sections is not None:
            for k in (set(self.sections) - set(spec.sections)):
                self.sections[k].validate(many_sections, validator, ancestors_names + (k,))

        return self

# ---------------------------------------------------------------------------------------------------------------------


def config_from_dict(d):
    return Section().from_dict(d)


def config_from_iter(lines, global_config=None, max_depth=0):
    return Section().from_iter(lines, global_config, max_depth)


def config_from_file(filename, global_config=None, max_depth=0):
    with open(filename) as f:
        return config_from_iter(f, global_config, max_depth)


def config_from_string(string, global_config=None, max_depth=0):
    return config_from_iter(iter(string.splitlines()), global_config, max_depth)
