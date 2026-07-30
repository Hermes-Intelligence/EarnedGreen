"""RECORDING STUB for the cloud helpers, standing in for the real AWS module.

The module under test imports `list_files`, `fetch_file_contents` and `archive`
from this package path. In production these talk to S3; here they serve a
scripted in-memory drop folder and RECORD every call, because the graded
surface is WHAT THE ORCHESTRATION DECIDED TO DO (which files it fetched,
uploaded, archived, and in what order) — not any cloud side effect.

Fully offline, zero dependencies, zero network. Tests configure it via
`_reset(files, contents)` and read `EVENTS`.
"""

QUEUE: list[str] = []
CONTENTS: dict[str, str] = {}
EVENTS: list[str] = []


def _reset(files, contents):
    QUEUE.clear()
    QUEUE.extend(files)
    CONTENTS.clear()
    CONTENTS.update(contents)
    EVENTS.clear()


def list_files(prefix):
    EVENTS.append(f"list:{prefix}")
    return list(QUEUE)


def fetch_file_contents(file):
    EVENTS.append(f"fetch:{file}")
    return CONTENTS.get(file, "")


def archive(file):
    EVENTS.append(f"archive:{file}")
