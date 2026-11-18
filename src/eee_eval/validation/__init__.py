"""EEE validation package.

Public API:
    SchemaValidator  — validate JSON records against eval.schema.json
    AutoFixer        — heuristic repairs for common schema issues
    FileValidator    — orchestrate validate → fix → re-validate for one file
    BatchValidator   — validate all JSON files in a directory tree
    validate_record  — check extracted values against paper HTML
    AuditRunner      — run comprehensive quality checks
"""
from eee_eval.validation.quality_audit import AuditRunner, RecordLoader
from eee_eval.validation.schema import (
    AutoFixer,
    BatchValidator,
    FileValidator,
    SchemaValidator,
)
from eee_eval.validation.validate_extractions import validate_record

__all__ = [
    "AuditRunner",
    "AutoFixer",
    "BatchValidator",
    "FileValidator",
    "RecordLoader",
    "SchemaValidator",
    "validate_record",
]
