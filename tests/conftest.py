import pytest
import inspect
import curio
import os

import logger

test_kernel = None


def _get_kernel():
    global test_kernel
    if test_kernel is None:
        test_kernel = curio.Kernel()
    return test_kernel


@pytest.fixture(scope="session")
def kernel_fixture():
    return _get_kernel()


@pytest.fixture(scope="function", autouse=True)
def log_function():
    """
    Logs currently running name of test-function
    """
    logger.info("Current test: " + os.environ.get('PYTEST_CURRENT_TEST'))


@pytest.mark.tryfirst
def pytest_pycollect_makeitem(collector, name, obj):
    """
    From https://docs.pytest.org/en/latest/reference.html
    return custom item/collector for a python object in a module, or None
    Stops at first non-None result, see firstresult: stop at first non-None result
    """
    if collector.funcnamefilter(name) and inspect.iscoroutinefunction(obj):
        item = pytest.Function.from_parent(name=name, parent=collector)
        if 'curio' in item.keywords:
            return list(collector._genfunctions(name, obj))


@pytest.mark.tryfirst
def pytest_pyfunc_call(pyfuncitem):
    """
    From https://docs.pytest.org/en/latest/reference.html
    call underlying test function.
    Stops at first non-None result, see firstresult: stop at first non-None result
    """
    _test_kernel = _get_kernel()
    if 'curio' in pyfuncitem.keywords:
        funcargs = pyfuncitem.funcargs
        testargs = {arg: funcargs[arg] for arg in pyfuncitem._fixtureinfo.argnames}
        fut = pyfuncitem.obj(**testargs)
        try:
            _test_kernel.run(fut)
        except curio.TaskError as e:
            raise e.__cause__ from e
        return True


def pytest_configure(config):
    # register an additional marker
    config.addinivalue_line(
        "markers", "curio: Asynchronous test functions"
    )


def pytest_sessionfinish(session, exitstatus):
    """ whole test run finishes. """
    if test_kernel is not None:
        test_kernel.run(shutdown=True)
