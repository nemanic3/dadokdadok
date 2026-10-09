"""Legacy signal module kept importable without modifying stored counters.

Goal progress is read-only and dynamically derived in goal.statistics. Importing
this module must never reinterpret unknown legacy periods or mutate their rows.
"""
