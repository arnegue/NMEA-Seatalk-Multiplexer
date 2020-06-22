import pytest
import inspect
import curio

test_kernel = None


@pytest.mark.tryfirst
def pytest_pycollect_makeitem(collector, name, obj):
    """
    From https://docs.pytest.org/en/latest/reference.html
    return custom item/collector for a python object in a module, or None
    Stops at first non-None result, see firstresult: stop at first non-None result
    """
    if collector.funcnamefilter(name) and inspect.iscoroutinefunction(obj):
        item = pytest.Function(name, parent=collector)
        if 'curio' in item.keywords:
            return list(collector._genfunctions(name, obj))


@pytest.mark.tryfirst
def pytest_pyfunc_call(pyfuncitem):
    """
    From https://docs.pytest.org/en/latest/reference.html
    call underlying test function.
    Stops at first non-None result, see firstresult: stop at first non-None result
    """
    global test_kernel
    if test_kernel is None:
        test_kernel = curio.Kernel()
    if 'curio' in pyfuncitem.keywords:
        funcargs = pyfuncitem.funcargs
        testargs = {arg: funcargs[arg] for arg in pyfuncitem._fixtureinfo.argnames}
        fut = pyfuncitem.obj(**testargs)
        test_kernel.run(fut)
        return True


def pytest_configure(config):
    # register an additional marker
    config.addinivalue_line(
        "markers", "curio: Asynchronous test functions"
    )


def pytest_sessionfinish(session, exitstatus):
    """ whole test run finishes. """
    test_kernel.run(shutdown=True)
