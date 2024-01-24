# --
# Copyright (c) 2008-2024 Net-ng.
# All rights reserved.
#
# This software is licensed under the BSD License, as described in
# the file LICENSE.txt, which you should have received as part of
# this distribution.
# --

import pytest

from nagare.config import config_from_string, ParseError, SectionError


def test_parse1():
    c = ''
    c = config_from_string(c)
    assert c == {}

    c = '        '
    c = config_from_string(c)
    assert c == {}

    c = '\n'
    c = config_from_string(c)
    assert c == {}

    c = '    \n     \n           '
    c = config_from_string(c)
    assert c == {}

    c = '# Comment'
    c = config_from_string(c)
    assert c == {}

    c = '        # Comment'
    c = config_from_string(c)
    assert c == {}

    c = '\n#Comment'
    c = config_from_string(c)
    assert c == {}

    c = '    \n     # Comment    \n           # Comment'
    c = config_from_string(c)
    assert c == {}


def test_parse2():
    c = '[]'
    with pytest.raises(ParseError, match='line #1'):
        config_from_string(c)

    c = '''["section]'''
    with pytest.raises(ParseError, match='line #1'):
        config_from_string(c)

    c = '''[section"]'''
    with pytest.raises(ParseError, match='line #1'):
        config_from_string(c)

    c = '''["sfsfsf']'''
    with pytest.raises(ParseError, match='line #1'):
        config_from_string(c)

    c = '''['sfsfsf"]''' ''
    with pytest.raises(ParseError, match='line #1'):
        config_from_string(c)

    c = 'abcd'
    with pytest.raises(ParseError, match='line #1'):
        config_from_string(c)

    c = '\nabcd'
    with pytest.raises(ParseError, match='line #2'):
        config_from_string(c)


def test_parse3():
    c = '''
    [section 1]
    [    section 2   ]
    ["section 3"]
    [    "section 4"   ]
    ['section 5']
    [    'section 6'   ]
    '''
    c = config_from_string(c)
    assert c['section 1'] == {}
    assert c['section 2'] == {}
    assert c['section 3'] == {}
    assert c['section 4'] == {}
    assert c['section 5'] == {}
    assert c['section 6'] == {}

    c = '''[section1]#Comment
        [[section 1-1]]  # Comment
        [[section 1-2]]  # [section]
      [section2]  # ['section']
        [[section 2-1]]  # ["section"]
        [[section 2-2]]
    '''
    c = config_from_string(c)
    assert (len(c['section1']) == 0) and (len(c['section1'].sections) == 2)
    assert c['section1']['section 1-1'] == {}
    assert c['section1']['section 1-2'] == {}

    assert (len(c['section2']) == 0) and (len(c['section2'].sections) == 2)
    assert c['section2']['section 2-1'] == {}
    assert c['section2']['section 2-2'] == {}


def test_parse4():
    c = '''
    [section]
    [[section2]
    '''
    with pytest.raises(ParseError, match='depth'):
        c = config_from_string(c)

    c = '''
    [section]
    [section2]]
    '''
    with pytest.raises(ParseError, match='depth'):
        c = config_from_string(c)


def test_parse5():
    c = '''
    [section]
    [[[section2]]]
    '''
    with pytest.raises(ParseError, match='nested'):
        c = config_from_string(c)


def test_parse6():
    c = '''
    [section]
    [section]
    '''
    with pytest.raises(SectionError, match='duplicate section name'):
        c = config_from_string(c)

    c = '''
    [section]
    [[section1]]
    [[[section3]]]
    [[section1]]
    '''
    with pytest.raises(SectionError, match='duplicate section name'):
        c = config_from_string(c)
