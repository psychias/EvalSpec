"""validate_outputs.py — thin wrapper delegating to schema.py.

DEPRECATED: Use `python -m eee_eval.validation.schema` instead.
Kept for backward compatibility with existing task runners.
"""
import sys

from eee_eval.paths import DATA_DIR
from eee_eval.validation.schema import (
    AutoFixer,
    BatchValidator,
    FileValidator,
    SchemaValidator,
)


def main() -> None:
    sv = SchemaValidator()
    fixer = AutoFixer()
    fv = FileValidator(sv, fixer, fix_mode=False)
    bv = BatchValidator(fv)
    report = bv.run(DATA_DIR, quiet=True)

    passed = report["valid"] + report.get("fixed", 0)
    failed = report.get("invalid", 0)

    print(f"schema validation: {passed} passed, {failed} failed")
    if failed:
        for r in report.get("files", []):
            if r.get("status") == "invalid":
                print(f"  FAIL {r['path']}: {r.get('error', 'unknown')}")
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
