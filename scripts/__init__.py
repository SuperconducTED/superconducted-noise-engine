"""Standalone analysis and diagnostic scripts.

Not shipped: ``[tool.hatch.build.targets.wheel]`` packages only
``src/superconducted``, so this file does not reach the wheel.

It exists so ``scripts`` resolves as one package rather than as both
``first_ensemble_run`` and ``scripts.first_ensemble_run``, which mypy rejects
as "source file found twice under different module names". Without it,
``[tool.mypy] files`` has to name each script individually — and the one added
without remembering to do that silently escapes type-checking, which is exactly
how ``canonical_snapshot_digest.py`` went unchecked when it was written.
"""
