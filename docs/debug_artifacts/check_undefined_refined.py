import ast
import sys
import os
from pathlib import Path

project = Path(r'd:\cursor\HarmonyOS\Github project\TradingAgents-main')

files = [
    project / 'tradingagents/screener/engine.py',
    project / 'tradingagents/screener/universe.py',
    project / 'tradingagents/screener/data_access.py',
    project / 'tradingagents/screener/merger.py',
    project / 'tradingagents/screener/deep_analyzer.py',
    project / 'tradingagents/screener/strategies/technical.py',
    project / 'tradingagents/screener/strategies/policy.py',
    project / 'tradingagents/screener/strategies/smart_money.py',
    project / 'cli/screener/run_impl.py',
    project / 'cli/screener/app.py',
]

# Built-in names that are always available in Python
BUILTINS = {
    'abs', 'all', 'any', 'ascii', 'bin', 'bool', 'breakpoint', 'bytearray', 'bytes',
    'callable', 'chr', 'classmethod', 'compile', 'complex', 'delattr', 'dict', 'dir',
    'divmod', 'enumerate', 'eval', 'exec', 'filter', 'float', 'format', 'frozenset',
    'getattr', 'globals', 'hasattr', 'hash', 'help', 'hex', 'id', 'input', 'int',
    'isinstance', 'issubclass', 'iter', 'len', 'list', 'locals', 'map', 'max',
    'memoryview', 'min', 'next', 'object', 'oct', 'open', 'ord', 'pow', 'print',
    'property', 'range', 'repr', 'reversed', 'round', 'set', 'setattr', 'slice',
    'sorted', 'staticmethod', 'str', 'sum', 'super', 'tuple', 'type', 'vars', 'zip',
    # Exception types
    'BaseException', 'Exception', 'TypeError', 'ValueError', 'KeyError', 'IndexError',
    'AttributeError', 'RuntimeError', 'OSError', 'FileNotFoundError', 'PermissionError',
    'NotImplementedError', 'StopIteration', 'ZeroDivisionError', 'OverflowError',
    'FloatingPointError', 'AssertionError', 'ImportError', 'ModuleNotFoundError',
    'IndentationError', 'SyntaxError', 'SystemExit', 'KeyboardInterrupt', 'GeneratorExit',
    'ConnectionError', 'BrokenPipeError', 'ConnectionResetError', 'TimeoutError',
    'Warning', 'UserWarning', 'DeprecationWarning', 'FutureWarning',
    # Special names
    '__name__', '__file__', '__builtins__', '__doc__', '__package__', '__loader__',
    '__spec__', '__annotations__', '__dict__', '__slots__', '__weakref__',
    # Ellipsis and NotImplemented
    'Ellipsis', 'NotImplemented', 'True', 'False', 'None',
    # Context managers
    'with', 'as',
}

# Typing module names that are commonly used
TYPING_NAMES = {
    'Any', 'Dict', 'List', 'Tuple', 'Set', 'FrozenSet', 'Optional', 'Union',
    'Callable', 'Iterable', 'Iterator', 'Generator', 'Sequence', 'Mapping',
    'Type', 'ClassVar', 'Generic', 'Protocol', 'NamedTuple', 'TypedDict',
    'Literal', 'Overload', 'Final', 'Cast', 'NoReturn', 'Optional',
    'OrderedDict', 'Counter', 'Deque', 'IO', 'TextIO', 'BinaryIO',
    'Pattern', 'Match', 'FrozenSet',
}


class UndefinedNameChecker(ast.NodeVisitor):
    def __init__(self, filename):
        self.filename = filename
        self.errors = []
        self._scope_stack = []
        self._defined = {}
        self._imports = set()
        self._future_imports = set()
        
    def _get_scope_name(self):
        return '.'.join(self._scope_stack)
        
    def _is_builtin(self, name):
        return name in BUILTINS
        
    def _is_typing_name(self, name):
        return name in TYPING_NAMES
        
    def visit_Module(self, node):
        self._defined[''] = set()
        for child in node.body:
            if isinstance(child, ast.Import):
                for alias in child.names:
                    imported = alias.asname or alias.name.split('.')[0]
                    self._defined[''].add(imported)
                    self._imports.add(imported)
            elif isinstance(child, ast.ImportFrom):
                if child.module == '__future__':
                    for alias in child.names:
                        self._future_imports.add(alias.name)
                        self._defined[''].add(alias.name)
                else:
                    for alias in child.names:
                        name = alias.asname or alias.name
                        self._defined[''].add(name)
                        self._imports.add(name)
        self.generic_visit(node)
        
    def visit_FunctionDef(self, node):
        self._scope_stack.append('func:' + node.name)
        func_defined = set(arg.arg for arg in node.args.args)
        self._defined[self._get_scope_name()] = func_defined.copy()
        # Check default args
        for default in node.args.defaults:
            self._check_node(default, func_defined, 'default_arg')
        for arg in node.args.args:
            self._check_node(arg, func_defined, 'arg')
        self.generic_visit(node)
        self._scope_stack.pop()
        
    def visit_AsyncFunctionDef(self, node):
        self.visit_FunctionDef(node)
        
    def visit_ClassDef(self, node):
        self._scope_stack.append('class:' + node.name)
        class_defined = set()
        for item in node.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                class_defined.add(item.name)
            elif isinstance(item, ast.Assign):
                for target in item.targets:
                    if isinstance(target, ast.Name):
                        class_defined.add(target.id)
        self._defined[self._get_scope_name()] = class_defined
        self.generic_visit(node)
        self._scope_stack.pop()
        
    def _check_node(self, node, defined, ctx):
        class Checker(ast.NodeVisitor):
            def __init__(self, errors, filename, scope, defined, ctx, checker):
                self.errors = errors
                self.filename = filename
                self.scope = scope
                self.defined = defined
                self.ctx = ctx
                self.checker = checker
                
            def visit_Name(self, node):
                if isinstance(node.ctx, ast.Store):
                    return
                if isinstance(node.ctx, ast.Param):
                    return
                name = node.id
                if self.checker._is_builtin(name):
                    return
                if self.checker._is_typing_name(name) and name in self.checker._imports:
                    return
                if name not in self.defined:
                    self.errors.append({
                        'file': self.filename,
                        'scope': self.scope,
                        'name': name,
                        'ctx': self.ctx,
                        'line': node.lineno,
                        'col': node.col_offset,
                    })
                self.generic_visit(node)
                
            def visit_FunctionDef(self, node):
                pass
            def visit_AsyncFunctionDef(self, node):
                pass
            def visit_ClassDef(self, node):
                pass
            def visit_Lambda(self, node):
                pass
            def visit_For(self, node):
                pass
            def visit_AsyncFor(self, node):
                pass
            def visit_While(self, node):
                pass
            def visit_If(self, node):
                pass
            def visit_Try(self, node):
                pass
            def visit_With(self, node):
                pass
                
        v = Checker(self.errors, self.filename, self._get_scope_name(), defined, ctx, self)
        v.visit(node)
        
    def visit_For(self, node):
        self._scope_stack.append('for')
        scope_key = self._get_scope_name()
        current_defs = self._defined.get(scope_key, set()).copy()
        self._check_node(node.iter, current_defs, 'for_iter')
        if isinstance(node.target, ast.Name):
            current_defs.add(node.target.id)
        self.generic_visit(node)
        self._scope_stack.pop()
        
    def visit_Assign(self, node):
        scope_key = self._get_scope_name()
        if scope_key not in self._defined:
            self._defined[scope_key] = set()
        for target in node.targets:
            if isinstance(target, ast.Name):
                self._defined[scope_key].add(target.id)
            elif isinstance(target, ast.Tuple):
                for t in target.elts:
                    if isinstance(t, ast.Name):
                        self._defined[scope_key].add(t.id)
        self.generic_visit(node)
        
    def visit_Name(self, node):
        if isinstance(node.ctx, ast.Load):
            scope_key = self._get_scope_name()
            all_defs = set()
            for k in self._defined:
                all_defs |= self._defined[k]
            # Also add typing imports
            all_defs |= self._imports
            if node.id not in all_defs and not self._is_builtin(node.id):
                if not self._is_typing_name(node.id):
                    self.errors.append({
                        'file': self.filename,
                        'scope': scope_key,
                        'name': node.id,
                        'ctx': 'load',
                        'line': node.lineno,
                        'col': node.col_offset,
                    })
        elif isinstance(node.ctx, ast.Store):
            scope_key = self._get_scope_name()
            if scope_key not in self._defined:
                self._defined[scope_key] = set()
            self._defined[scope_key].add(node.id)
        self.generic_visit(node)

results = []
for f in files:
    if not f.exists():
        results.append('SKIP (not found): ' + str(f))
        continue
    try:
        source = f.read_text(encoding='utf-8')
        tree = ast.parse(source)
    except SyntaxError as e:
        results.append(str(f) + ': SYNTAX ERROR: ' + str(e))
        continue
        
    checker = UndefinedNameChecker(str(f))
    try:
        checker.visit(tree)
    except Exception as e:
        import traceback
        results.append(str(f) + ': AST VISIT ERROR: ' + str(e))
        traceback.print_exc()
        continue
        
    for err in checker.errors:
        scope = err['scope']
        results.append(
            err['file'] + ':' + str(err['line']) +
            ' [' + scope + '] ' +
            'undefined: ' + repr(err['name']) + ' (ctx=' + err['ctx'] + ')'
        )

for r in results:
    print(r)
print('---')
print('Total errors: ' + str(len(results)))