from pbt_runner.test_contract import unresolved_names


def test_missing_pandas_alias_is_reported_without_rewriting():
    source = 'def test_frame(run, x):\n    assert isinstance(run(x)[0], pd.DataFrame)\n'
    assert unresolved_names(source) == ['test_frame: unresolved names: pd']
    assert 'import' not in source


def test_local_imports_closures_comprehensions_and_builtins_are_valid():
    source = '''def test_frame(run, x):
    import pandas as pd
    result = run(x)
    def valid(item):
        return isinstance(item, pd.DataFrame)
    assert all(valid(item) for item in result)
'''
    assert unresolved_names(source) == []


def test_imports_do_not_leak_between_tests():
    source = '''def test_first(run, x):
    import pandas as pd
    assert isinstance(run(x)[0], pd.DataFrame)
def test_second(run, x):
    assert isinstance(run(x)[0], pd.DataFrame)
'''
    assert unresolved_names(source) == ['test_second: unresolved names: pd']


def test_module_import_does_not_satisfy_independent_function_contract():
    assert unresolved_names('import pandas as pd\ndef test_a(run,x): return pd.DataFrame()')


def test_syntax_errors_remain_errors():
    assert unresolved_names('def broken(') == ['invalid test source: SyntaxError']
