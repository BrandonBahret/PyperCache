"""Lightweight wall-clock profiler."""

import time
from typing import Dict


class Profiler:
    """Lightweight label-based wall-clock profiler.

    Usage::

        profiler = Profiler()
        profiler.start_profile("my_task")
        do_work()
        profiler.end_profile("my_task")  # prints elapsed time if > 1 ms
    """

    def __init__(self) -> None:
        self.start_times: Dict[str, float] = {}

    def start_profile(self, label: str) -> None:
        """Record the start time for *label*.

        Args:
            label: An arbitrary string identifying the profiling session.
        """
        self.start_times[label] = time.time()

    def end_profile(self, label: str) -> None:
        """End the session for *label* and print the elapsed time.

        Elapsed times below 1 ms are suppressed to reduce noise. If no
        matching ``start_profile`` call exists a warning is printed instead.

        Args:
            label: The label passed to the corresponding ``start_profile`` call.
        """
        if label not in self.start_times:
            print(f"No profiling session found for label '{label}'.")
            return

        elapsed = time.time() - self.start_times[label]
        if elapsed > 0.001:
            print(f"Time elapsed for '{label}': {elapsed:.4f} seconds")
