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

class UndefinedNameChecker(ast.NodeVisitor):
    def __init__(self, filename):
        self.filename = filename
        self.errors = []
        self._scope_stack = []
        self._defined = {}
        
    def _get_scope_name(self):
        return '.'.join(self._scope_stack)
        
    def visit_Module(self, node):
        self._defined[''] = set()
        for child in node.body:
            if isinstance(child, ast.Import):
                for alias in child.names:
                    self._defined[''].add(alias.asname or alias.name.split('.')[0])
            elif isinstance(child, ast.ImportFrom):
                for alias in child.names:
                    self._defined[''].add(alias.asname or alias.name)
        self.generic_visit(node)
        
    def visit_FunctionDef(self, node):
        self._scope_stack.append('func:' + node.name)
        func_defined = set(arg.arg for arg in node.args.args)
        self._defined[self._get_scope_name()] = func_defined
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
        self._defined[self._get_scope_name()] = set()
        for item in node.body:
            if isinstance(item, ast.FunctionDef) or isinstance(item, ast.AsyncFunctionDef):
                pass
            elif isinstance(item, ast.Assign):
                for target in item.targets:
                    if isinstance(target, ast.Name):
                        self._defined[self._get_scope_name()].add(target.id)
        self.generic_visit(node)
        self._scope_stack.pop()
        
    def _check_node(self, node, defined, ctx):
        class Checker(ast.NodeVisitor):
            def __init__(self, errors, filename, scope, defined, ctx):
                self.errors = errors
                self.filename = filename
                self.scope = scope
                self.defined = defined
                self.ctx = ctx
                
            def visit_Name(self, node):
                if isinstance(node.ctx, ast.Store):
                    return
                if isinstance(node.ctx, ast.Param):
                    return
                name = node.id
                if name in ('True', 'False', 'None', 'Ellipsis', 'break', 'continue'):
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
                
        v = Checker(self.errors, self.filename, self._get_scope_name(), defined, ctx)
        v.visit(node)
        
    def visit_For(self, node):
        self._scope_stack.append('for')
        scope_key = self._get_scope_name()
        current_defs = self._defined.get(scope_key, set())
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
            if node.id not in all_defs:
                if node.id not in ('True', 'False', 'None', 'Ellipsis'):
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
        results.append(str(f) + ': AST VISIT ERROR: ' + str(e))
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