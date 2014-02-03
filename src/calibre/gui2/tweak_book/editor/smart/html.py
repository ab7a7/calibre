#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2014, Kovid Goyal <kovid at kovidgoyal.net>'

import sys
from operator import itemgetter
from . import NullSmarts

from PyQt4.Qt import QTextEdit

get_offset = itemgetter(0)

class Tag(object):

    def __init__(self, start_block, tag_start, end_block, tag_end, self_closing=False):
        self.start_block, self.end_block = start_block, end_block
        self.start_offset, self.end_offset = tag_start.offset, tag_end.offset
        tag = tag_start.name or tag_start.prefix
        if tag_start.name and tag_start.prefix:
            tag = tag_start.prefix + ':' + tag
        self.name = tag
        self.self_closing = self_closing

def next_tag_boundary(block, offset, forward=True):
    while block.isValid():
        ud = block.userData()
        if ud is not None:
            tags = sorted(ud.tags, key=get_offset, reverse=not forward)
            for boundary in tags:
                if forward and boundary.offset > offset:
                    return block, boundary
                if not forward and boundary.offset < offset:
                    return block, boundary
        block = block.next() if forward else block.previous()
        offset = -1 if forward else sys.maxint
    return None, None

def find_closest_containing_tag(block, offset, max_tags=2000):
    ''' Find the closest containing tag. To find it, we search for the first
    opening tag that does not have a matching closing tag before the specified
    position. Search through at most max_tags. '''
    prev_tag_boundary = lambda b, o: next_tag_boundary(b, o, forward=False)

    block, boundary = prev_tag_boundary(block, offset)
    if block is None:
        return None
    if boundary.is_start:
        # We are inside a tag, therefore the containing tag is the parent tag of
        # this tag
        return find_closest_containing_tag(block, boundary.offset)
    stack = []
    block, tag_end = block, boundary
    while block is not None and max_tags > 0:
        sblock, tag_start = prev_tag_boundary(block, tag_end.offset)
        if sblock is None or not tag_start.is_start:
            break
        if tag_start.closing:  # A closing tag of the form </a>
            stack.append((tag_start.prefix, tag_start.name))
        elif tag_end.self_closing:  # A self closing tag of the form <a/>
            pass  # Ignore it
        else:  # An opening tag, hurray
            try:
                prefix, name = stack.pop()
            except IndexError:
                prefix = name = None
            if (prefix, name) != (tag_start.prefix, tag_start.name):
                # Either we have an unbalanced opening tag or a syntax error, in
                # either case terminate
                return Tag(sblock, tag_start, block, tag_end)
        block, tag_end = prev_tag_boundary(sblock, tag_start.offset)
        max_tags -= 1
    return None  # Could not find a containing tag

def find_closing_tag(tag, max_tags=4000):
    ''' Find the closing tag corresponding to the specified tag. To find it we
    search for the first closing tag after the specified tag that does not
    match a previous opening tag. Search through at most max_tags. '''

    stack = []
    block, offset = tag.end_block, tag.end_offset
    while block.isValid() and max_tags > 0:
        block, tag_start = next_tag_boundary(block, offset)
        if block is None or not tag_start.is_start:
            break
        endblock, tag_end = next_tag_boundary(block, tag_start.offset)
        if block is None or tag_end.is_start:
            break
        if tag_start.closing:
            try:
                prefix, name = stack.pop()
            except IndexError:
                prefix = name = None
            if (prefix, name) != (tag_start.prefix, tag_start.name):
                return Tag(block, tag_start, endblock, tag_end)
        elif tag_end.self_closing:
            pass
        else:
            stack.append((tag_start.prefix, tag_start.name))
        block, offset = endblock, tag_end.offset
        max_tags -= 1
    return None

class HTMLSmarts(NullSmarts):

    def get_extra_selections(self, editor):
        ans = []

        def add_tag(tag):
            a = QTextEdit.ExtraSelection()
            a.cursor, a.format = editor.textCursor(), editor.match_paren_format
            a.cursor.setPosition(tag.start_block.position() + tag.start_offset)
            a.cursor.setPosition(tag.end_block.position() + tag.end_offset + 1, a.cursor.KeepAnchor)
            ans.append(a)

        c = editor.textCursor()
        block, offset = c.block(), c.positionInBlock()
        tag = find_closest_containing_tag(block, offset)
        if tag is not None:
            add_tag(tag)
            tag = find_closing_tag(tag)
            if tag is not None:
                add_tag(tag)
        return ans
