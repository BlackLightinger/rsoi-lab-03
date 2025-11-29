import time
from typing import Callable, Any, Optional


class CircuitOpenException(Exception):
    def __init__(self, service):
        self.service = service


class CircuitBreaker:
    def __init__(
        self,
        service,
        failure_threshold: int = 1,
        recovery_timeout: int = 1,
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout

        self.fail_count = 0
        self.state = "closed"  # closed | open | half-open
        self.open_since = None
        self.service = service

    def call(self, func: Callable, *args, **kwargs) -> Any:
        now = time.time()

        # ----- OPEN -----
        if self.state == "open":
            if now - self.open_since >= self.recovery_timeout:
                self.state = "half-open"
            else:
                raise CircuitOpenException(self.service)

        try:
            result = func(*args, **kwargs)
        except Exception:
            self.fail_count += 1

            if self.state == "half-open":
                self.state = "open"
                self.open_since = time.time()
                raise CircuitOpenException(self.service)

            if self.fail_count >= self.failure_threshold:
                self.state = "open"
                self.open_since = time.time()
                raise CircuitOpenException(self.service)

            # Re-raise original exception (timeout, 500, etc.)
            raise CircuitOpenException(self.service)

        # ----- SUCCESS -----
        self.fail_count = 0
        self.state = "closed"
        return result