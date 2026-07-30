"""Run the workspace's ETL runner over the scenario corpus; print event streams.

Executed INSIDE a workspace (cwd = workspace) as a subprocess of the grader or
the derivation tool: `python etl_runner.py <scenarios.json>`. Emits one JSON
object {scenario_id: [events...] | {"__error__": ...}} on stdout.

Isolation notes:
  * the import of the module under test is wrapped: a workspace whose src/
    crashes on import (the admission gate's hostile battery does exactly that)
    yields an __error__ stream per scenario instead of killing the runner —
    the grader must degrade per-dimension, never collapse;
  * each scenario is wrapped the same way; the terminal event records how the
    run ENDED (ok, or the exception type and message), because "raises at the
    end" vs "raises at the first bad file" is precisely the behaviour under
    test and must be visible in the stream.
"""
import json
import sys
import os

sys.path.insert(0, os.getcwd())
sys.path.insert(0, os.path.join(os.getcwd(), "src"))

from hermes_intelligence.hermes_tools.cloud import aws  # noqa: E402


def scripted_transform(content, file):
    aws.EVENTS.append(f"transform:{file}")
    if content == "BAD":
        raise ValueError(f"malformed drop: {file}")
    return f"T({content})"


def main() -> None:
    scenarios = json.loads(open(sys.argv[1], encoding="utf-8-sig").read())["scenarios"]
    streams = {}
    try:
        import etl_base
    except BaseException as error:  # noqa: BLE001 - hostile import must not kill the runner
        message = f"import failed: {type(error).__name__}: {error}"
        print(json.dumps({row["id"]: {"__error__": message} for row in scenarios}))
        return
    for row in scenarios:
        aws._reset(row["files"], row["contents"])
        uploads = []

        def scripted_upload(result):
            uploads.append(result)
            aws.EVENTS.append(f"upload:{result}")

        try:
            etl_base.run_etl("drop/", scripted_transform, scripted_upload, **row.get("kwargs", {}))
            aws.EVENTS.append("end:ok")
        except BaseException as error:  # noqa: BLE001 - the ending IS the observable
            aws.EVENTS.append(f"end:raise:{type(error).__name__}:{error}")
        streams[row["id"]] = list(aws.EVENTS)
    print(json.dumps(streams, ensure_ascii=False))


if __name__ == "__main__":
    main()
