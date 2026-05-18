"""Aer integration: the Factory/Ensemble bridge between the fuzzy pipeline
and Qiskit Aer.

Architectural invariant: Aer has no per-shot Python hook. Sample-level
uncertainty is realized at ensemble-construction time, not simulation time.
"""
