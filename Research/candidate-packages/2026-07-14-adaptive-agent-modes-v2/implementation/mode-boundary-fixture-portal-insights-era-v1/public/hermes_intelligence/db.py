"""Infrastructure seam (offline workspace copy): database access.

The live implementation is provided by the runtime/harness. These signatures
are the contract (see DATA.md): dict rows, %s paramstyle, read-only for the
insights layer. Do not modify this module.
"""


def _offline(*_a, **_k):
    raise RuntimeError("offline workspace: the runtime provides the live database seam")


def _connect(*a, **k):
    _offline()


def execute_query(sql, params=None):
    _offline()


def read_multiple_records(sql, params=None):
    _offline()


def read_single_record(sql, params=None):
    _offline()


def write_to_database(sql, params=None):
    _offline()


def update_database(sql, params=None):
    _offline()
