"""
There are some changes since curio 1.0
This is a file for some wrappers to get back the old behavior or to make some things easier
"""
import curio
import signal
import sys

import logger
from common.helper import Singleton
from common.watchdog import Watchdog
from common import settings


class TaskGroupWrapper(curio.TaskGroup):
    """
    Raise exception if one task failed
    Look https://github.com/dabeaz/curio/issues/314
    """
    async def __aexit__(self, ty, val, tb):
        result = await super().__aexit__(ty, val, tb)
        if not val:
            list_exceptions = [exception for exception in getattr(self, "exceptions", []) if exception is not None]
            if list_exceptions:
                if len(list_exceptions) > 1:
                    print(f"There are more than 1 exceptions: {len(list_exceptions)}\n Only raising first")
                raise list_exceptions[0]
        return result


class TaskWatcher(object, metaclass=Singleton):
    """
    Spawns tasks in background and watches them every x seconds (logs if tasks finishes)
    If enabled by settings, a watchdog will watch over the tasks. If a task stops, the watchdog won't be fed anymore
    """
    def __init__(self):
        self._daemon_tasks = []
        self._watch_interval_s = 30
        self.own_task_handle = None
        self._wd = None

        self.wd_settings = settings.Settings().Watchdog
        if self.wd_settings.Enable:
            if self.wd_settings.PreviousResets < self.wd_settings.MaxResets:
                self._wd = Watchdog.get_watchdog()(timeout=self.wd_settings.Timeout)
            else:
                logger.error(f"Not creating Watchdog. Device got reset {self.wd_settings.PreviousResets} times before.")

    @classmethod
    async def daemon_spawn(cls, task, *args):
        """
        Spawns a task in background and adds it to handler
        :param task: coroutine to spawn
        :param args: arguments to pass to task
        :return: handle of task
        """
        instance = cls()
        if not instance.own_task_handle:
            instance.own_task_handle = await curio.spawn(instance._watch_routine, daemon=True)
        task_handle = await curio.spawn(task, *args, daemon=True)
        instance._daemon_tasks.append(task_handle)
        return task_handle

    async def _watch_routine(self):
        """
        Runs in background, watches every daemon-spawned task and waits for it to finish.
        If any task finishes, it will be logged as warning or error (depending on its return)
        """
        watchdog_stop = False
        if self._wd:
            signal.signal(signal.SIGINT, self.exit)
            self._wd.start()
            self._watch_interval_s = self._wd.get_timeout() >> 2  # Half the watchdog's timeout
        try:
            while True:
                for task_handle in self._daemon_tasks:
                    task_str = f"{type(self).__name__}: TaskHandle {task_handle.name} with id {task_handle.id} "
                    try:
                        if task_handle.terminated:
                            task_str += "terminated"
                            if task_handle.exception:
                                task_str += " with exception:"
                                logger.exception(task_str, task_handle.exception)
                            else:
                                task_str += " without an exception"
                                logger.warn(task_str)
                            if self._wd:
                                return  # TODO quit
                    except Exception as e:
                        logger.exception(task_str + f". Could not identify task's state:", e)
                        if self._wd:
                            watchdog_stop = True
                            return  # TODO quit

                await curio.sleep(self._watch_interval_s)
                if self._wd:
                    self._wd.reset()
        finally:
            if watchdog_stop:
                self.wd_settings.PreviousResets += 1
                self.wd_settings.write_to_file()
            logger.error("TaskWatcher: Watch-Routine ended")

    def exit(self, sig, frame):
        self.wd_settings.PreviousResets = 0  # TODO does it also write to file?
        self._wd.exit()
        sys.exit(0)
