# Encoding: utf-8

# --
# Copyright (c) 2008-2024 Net-ng.
# All rights reserved.
#
# This software is licensed under the BSD License, as described in
# the file LICENSE.txt, which you should have received as part of
# this distribution.
# --


class ConfigError(ValueError):
    def __init__(self, error, line=None):
        self.error = error
        self.line = line

    @property
    def context(self):
        return ' line #{}'.format(self.line) if self.line else ''

    def __str__(self):
        return 'Error{}: {}'.format(self.context, self.error)


class ParseError(ConfigError):
    pass


class ContextualParseError(ParseError):
    def __init__(self, error, line=None, sections=(), name=None):
        super(ContextualParseError, self).__init__(error, line)

        self._sections = sections
        self.name = name

    @property
    def sections(self):
        sections = [(('[' * i) + section + (']' * i)) for i, section in enumerate(self._sections, 1)]
        if self.name:
            sections.append(self.name)

        return (' ' + (' / '.join(sections))) if sections else ''


class SpecificationError(ContextualParseError):
    @property
    def context(self):
        return super(SpecificationError, self).context + (' for specification{}'.format(self.sections))


class SectionError(ContextualParseError):
    @property
    def context(self):
        return super(SectionError, self).context + (' for section{}'.format(self.sections))


class ParameterError(SpecificationError):
    @property
    def context(self):
        return super(SpecificationError, self).context + (' for parameter{}'.format(self.sections))


class InterpolationError(ContextualParseError):
    @property
    def context(self):
        return super(InterpolationError, self).context + (' in section{}'.format(self.sections))


class DirectiveError(ContextualParseError):
    @property
    def context(self):
        return super(DirectiveError, self).context + (' in section{}'.format(self.sections))
