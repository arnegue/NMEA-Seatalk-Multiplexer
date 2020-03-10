"""
There are some changes since curio 1.0
This is a file for some wrappers to get back the old behavior or to make some things easier
"""
import curio


class TaskGroupWrapper(curio.TaskGroup):
    """
    Raise exception if one task failed
    Look https://github.com/dabeaz/curio/issues/314
    """
    async def __aexit__(self, ty, val, tb):
        result = await super().__aexit__(ty, val, tb)

        list_exceptions = [exception for exception in getattr(self, "exceptions", []) if exception is not None]
        if list_exceptions:
            if len(list_exceptions) > 1:
                print(f"There are more than 1 exception {len(list_exceptions)}\n Only raising first")
            raise list_exceptions[0]
        return result
