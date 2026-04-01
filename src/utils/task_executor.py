"""Task executor — context manager for pipeline task lifecycle."""

import traceback


class TaskExecutor:
    """
    Wraps a pipeline task with dependency checking, status logging, and error handling.

    Usage::

        executor = TaskExecutor(task_name, batch_id, dag_handler, monitor)
        with executor:
            if executor.can_run:
                result = my_task_function(...)
    """

    def __init__(self, task_name: str, block_name: str, dag_handler, monitor=None, session_name: str = None):
        self.task_name = task_name
        self.block_name = block_name
        self.dag_handler = dag_handler
        self.monitor = monitor
        self.session_name = session_name
        self.can_run: bool = False
        self.error_msg: str = None

    def __enter__(self):
        if self.dag_handler.can_run(self.task_name):
            self.can_run = True
            print(f"[{self.block_name}] ==> Running task: {self.task_name}")
            if self.monitor is not None:
                self.monitor.update(self.block_name, self.task_name, "RUNNING")
        return self

    def __exit__(self, exc_type, exc_value, tb):
        if not self.can_run:
            return

        if exc_type:
            self.error_msg = f"Task '{self.task_name}' failed: {exc_value}"
            print(f"ERROR: {self.error_msg}\n{traceback.format_exc()}")
            if self.monitor is not None:
                self.monitor.update(
                    self.block_name, self.task_name, "FAILURE", self.error_msg
                )
            return True  # suppress exception
        else:
            self.dag_handler.mark_completed(self.task_name)
            if self.monitor is not None:
                self.monitor.update(self.block_name, self.task_name, "SUCCESS")
        return False
