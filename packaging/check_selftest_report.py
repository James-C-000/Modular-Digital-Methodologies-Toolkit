"""Assert properties of a self-test JSON report in CI.

    python packaging/check_selftest_report.py report.json [--expect-missing-stdio]

--expect-missing-stdio: the app must have started without stdout/stderr (a
windowed launch with no inherited handles, as from Explorer or Finder), so
the report proves the log-file fallback was exercised.
"""
import json
import sys


def main(argv):
    path = argv[1]
    with open(path, encoding="utf-8") as f:
        report = json.load(f)
    problems = [f"check failed: {c['name']}: {c.get('error')}" for c in report["checks"] if not c["ok"]]
    if "--expect-missing-stdio" in argv:
        missing = set(report["info"].get("stdio_originally_missing", []))
        if missing != {"stdout", "stderr"}:
            problems.append(f"expected the app to start without stdout/stderr, missing were: {sorted(missing)};"
                            f" streams at launch: {report['info'].get('stdio_at_launch')}")
    for p in problems:
        print("ERROR:", p)
    print(f"{path}: {'OK' if not problems else 'FAILED'}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
