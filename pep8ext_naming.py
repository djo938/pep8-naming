# -*- coding: utf-8 -*-
"""Checker of PEP-8 Naming Conventions."""

import re
import sys
from collections import deque

try:
    import ast
    from ast import iter_child_nodes
except ImportError:
    from flake8.util import ast, iter_child_nodes

__version__ = '0.3.3'

WORDCASE = r'([A-Z][A-Z]?[a-z0-9]+)'
LOWERCAMELCASE = r'_?[a-z]+[0-9]*'+WORDCASE+'*'

# method + special method __main__, __not_zero__
METHODS_REGEX = re.compile(LOWERCAMELCASE+r'$')
SPECIAL_METHOD_REGEX = re.compile(r'__[a-z]+__$')

# variable, argument
LOWERCAMELCASE_REGEX = re.compile(LOWERCAMELCASE+r'$')

# constant
CONSTANT_REGEX = re.compile(r'[_A-Z]([A-Z0-9]+_?)*[A-Z0-9]+$')

# class
CLASS_REGEX = re.compile(r'_?'+WORDCASE+'+$')

SPLIT_IGNORED_RE = re.compile(r'[,\s]')


if sys.version_info[0] < 3:
    def _unpack_args(args):
        ret = []
        for arg in args:
            if isinstance(arg, ast.Tuple):
                ret.extend(_unpack_args(arg.elts))
            else:
                ret.append(arg.id)
        return ret

    def get_arg_names(node):
        return _unpack_args(node.args.args)
else:
    def get_arg_names(node):
        pos_args = [arg.arg for arg in node.args.args]
        kw_only = [arg.arg for arg in node.args.kwonlyargs]
        return pos_args + kw_only


class _ASTCheckMeta(type):
    def __init__(self, class_name, bases, namespace):
        try:
            self._checks.append(self())
        except AttributeError:
            self._checks = []


def _err(self, node, code):
    lineno, col_offset = node.lineno, node.col_offset
    if isinstance(node, ast.ClassDef):
        lineno += len(node.decorator_list)
        col_offset += 6
    elif isinstance(node, ast.FunctionDef):
        lineno += len(node.decorator_list)
        col_offset += 4
    return (lineno, col_offset, '%s %s' % (code, getattr(self, code)), self)
BaseASTCheck = _ASTCheckMeta('BaseASTCheck', (object,),
                             {'__doc__': "Base for AST Checks.", 'err': _err})


class NamingChecker(object):
    """Checker of PEP-8 Naming Conventions."""
    name = 'naming'
    version = __version__
    ignore_names = []

    def __init__(self, tree, filename):
        self.visitors = BaseASTCheck._checks
        self.parents = deque()
        self._node = tree

    @classmethod
    def add_options(cls, parser):
        ignored = ','.join(cls.ignore_names)
        parser.add_option('--ignore-names', default=ignored,
                          action='store', type='string',
                          help="Names that should be ignored.")
        parser.config_options.append('ignore-names')

    @classmethod
    def parse_options(cls, options):
        cls.ignore_names = SPLIT_IGNORED_RE.split(options.ignore_names)

    def run(self):
        return self.visit_tree(self._node) if self._node else ()

    def visit_tree(self, node):
        for error in self.visit_node(node):
            yield error
        self.parents.append(node)
        for child in iter_child_nodes(node):
            for error in self.visit_tree(child):
                yield error
        self.parents.pop()

    def visit_node(self, node):
        if isinstance(node, ast.ClassDef):
            self.tag_class_functions(node)
        elif isinstance(node, ast.FunctionDef):
            self.find_global_defs(node)

        method = 'visit_' + node.__class__.__name__.lower()
        parents = self.parents
        ignore_names = self.ignore_names
        for visitor in self.visitors:
            visitor_method = getattr(visitor, method, None)
            if visitor_method is None:
                continue
            for error in visitor_method(node, parents, ignore_names):
                yield error

    def tag_class_functions(self, cls_node):
        """Tag functions if they are methods, classmethods, staticmethods"""
        # tries to find all 'old style decorators' like
        # m = staticmethod(m)
        late_decoration = {}
        for node in iter_child_nodes(cls_node):
            if not (isinstance(node, ast.Assign) and
                    isinstance(node.value, ast.Call) and
                    isinstance(node.value.func, ast.Name)):
                continue
            func_name = node.value.func.id
            if func_name in ('classmethod', 'staticmethod'):
                meth = (len(node.value.args) == 1 and node.value.args[0])
                if isinstance(meth, ast.Name):
                    late_decoration[meth.id] = func_name

        # iterate over all functions and tag them
        for node in iter_child_nodes(cls_node):
            if not isinstance(node, ast.FunctionDef):
                continue

            node.function_type = 'method'
            if node.name == '__new__':
                node.function_type = 'classmethod'

            if node.name in late_decoration:
                node.function_type = late_decoration[node.name]
            elif node.decorator_list:
                names = [d.id for d in node.decorator_list
                         if isinstance(d, ast.Name) and
                         d.id in ('classmethod', 'staticmethod')]
                if names:
                    node.function_type = names[0]

    def find_global_defs(self, func_def_node):
        global_names = set()
        nodes_to_check = deque(iter_child_nodes(func_def_node))
        while nodes_to_check:
            node = nodes_to_check.pop()
            if isinstance(node, ast.Global):
                global_names.update(node.names)

            if not isinstance(node, (ast.FunctionDef, ast.ClassDef)):
                nodes_to_check.extend(iter_child_nodes(node))
        func_def_node.global_names = global_names


class ClassNameCheck(BaseASTCheck):
    """
    Almost without exception, class names use the CapWords convention.

    Classes for internal use have a leading underscore in addition.
    """
    check = CLASS_REGEX.match
    N801 = "class names should use UpperCamelCase convention"

    def visit_classdef(self, node, parents, ignore=None):
        if not self.check(node.name):
            yield self.err(node, 'N801')


class FunctionNameCheck(BaseASTCheck):
    """
    Function names should be lowercamelcase, with words separated by
    underscores as necessary to improve readability.
    Functions *not* beeing methods '__' in front and back are not allowed.

    mixedCase is allowed only in contexts where that's already the
    prevailing style (e.g. threading.py), to retain backwards compatibility.
    """
    check = METHODS_REGEX.match
    check2 = SPECIAL_METHOD_REGEX.match
    N802 = "function name should be lowerCamelCase or __lowercase__"

    def visit_functiondef(self, node, parents, ignore=None):
        name = node.name
        if ignore and name in ignore:
            return

        if not self.check(name) and not self.check2(name):
            yield self.err(node, 'N802')


class FunctionArgNamesCheck(BaseASTCheck):
    """
    The argument names of a function should be lowercamelcase, with words
    separated by underscores.

    A classmethod should have 'cls' as first argument.
    A method should have 'self' as first argument.
    """
    check = LOWERCAMELCASE_REGEX.match
    N803 = "argument name should be lowerCamelCase"
    N804 = "first argument of a classmethod should be named 'cls'"
    N805 = "first argument of a method should be named 'self'"

    def visit_functiondef(self, node, parents, ignore=None):

        def arg_name(arg):
            return getattr(arg, 'arg', arg)

        kwarg = arg_name(node.args.kwarg)
        if kwarg is not None:
            if not self.check(kwarg):
                yield self.err(node, 'N803')
                return

        vararg = arg_name(node.args.vararg)
        if vararg is not None:
            if not self.check(vararg):
                yield self.err(node, 'N803')
                return

        arg_names = get_arg_names(node)
        if not arg_names:
            return
        function_type = getattr(node, 'function_type', 'function')

        if function_type == 'method':
            if arg_names[0] != 'self':
                yield self.err(node, 'N805')
        elif function_type == 'classmethod':
            if arg_names[0] != 'cls':
                yield self.err(node, 'N804')
        for arg in arg_names:
            if not self.check(arg):
                yield self.err(node, 'N803')
                return


class ImportAsCheck(BaseASTCheck):
    """
    Don't change the naming convention via an import
    """

    check_const = CONSTANT_REGEX.match
    check_var = LOWERCAMELCASE_REGEX.match
    check_meth = METHODS_REGEX.match
    check_class = CLASS_REGEX.match

    N811 = "CONSTANT_CASE imported as non CONSTANT_CASE"
    N812 = "lowerCamelCase imported as non lowerCamelCase"
    N813 = "lowerCamelCase imported as non lowerCamelCasen"
    N814 = "Upper camel case imported as non upper camel case"

    def visit_importfrom(self, node, parents, ignore=None):
        for name in node.names:
            if not name.asname:
                continue

            if self.check_const(name.name):
                if not self.check_const(name.asname):
                    yield self.err(node, 'N811')
            elif self.check_var(name.name):
                if not self.check_var(name.asname):
                    yield self.err(node, 'N812')
            elif self.check_meth(name.name):
                if not self.check_meth(name.asname):
                    yield self.err(node, 'N813')
            elif self.check_class(name.name):
                if not self.check_class(name.asname):
                    yield self.err(node, 'N814')


class VariablesInFunctionCheck(BaseASTCheck):
    """
    Local variables in functions should be lowercamelcase
    """
    check = LOWERCAMELCASE_REGEX.match
    N806 = "variable in function should be lowerCamelCase"

    def visit_assign(self, node, parents, ignore=None):
        for parent_func in reversed(parents):
            if isinstance(parent_func, ast.ClassDef):
                return
            if isinstance(parent_func, ast.FunctionDef):
                break
        else:
            return
        for target in node.targets:
            name = isinstance(target, ast.Name) and target.id
            if not name or name in parent_func.global_names:
                return
            if not self.check(name):
                if isinstance(node.value, ast.Call):
                    if isinstance(node.value.func, ast.Attribute):
                        if node.value.func.attr == 'namedtuple':
                            return
                    elif isinstance(node.value.func, ast.Name):
                        if node.value.func.id == 'namedtuple':
                            return

                yield self.err(target, 'N806')
