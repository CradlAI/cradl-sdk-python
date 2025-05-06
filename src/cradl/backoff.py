import functools
import time
from typing import Union, Type, Callable


def exponential_backoff(
    exceptions: Union[tuple[Type[Exception]], Type[Exception]],
    base_wait: int = 1,
    max_time: float = None,
    max_tries: int = None,
    rate: int = 2,
    giveup: Callable = lambda e: False,
) -> Callable:
    # Return a function which decorates a target with a retry loop.
    # Adapted from https://github.com/litl/backoff
    # Backoff is exponential: t = base_wait * rate ^ (trial #)
    if not max_time and not max_tries:
        raise ValueError('Must set at least one of max_time or max_tries')

    def decorate(target):
        @functools.wraps(target)
        def retry(*args, **kwargs):
            start = time.time()
            trial_no = 0
            while True:
                try:
                    ret = target(*args, **kwargs)
                except exceptions as e:
                    elapsed = time.time() - start
                    next_wait_seconds = base_wait * rate ** trial_no
                    last_try_done = max_tries and trial_no == max_tries - 1
                    no_time_for_next_try = max_time and (elapsed + next_wait_seconds > max_time)
                    if giveup(e) or last_try_done or no_time_for_next_try:
                        raise

                    time.sleep(next_wait_seconds)
                else:
                    return ret
                trial_no += 1
        return retry
    return decorate
