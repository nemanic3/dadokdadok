"""Classify only the intended non-primary unique constraint on either DB."""
from django.db import connection


def is_unique_conflict(error, table, columns):
    if connection.vendor == 'sqlite':
        expected = ', '.join(f'{table}.{column}' for column in columns)
        return str(error) == f'UNIQUE constraint failed: {expected}'
    if connection.vendor == 'postgresql':
        cause = error.__cause__
        diagnostic = getattr(cause, 'diag', None)
        if (getattr(cause, 'sqlstate', None) != '23505' or
                getattr(diagnostic, 'table_name', None) != table):
            return False
        with connection.cursor() as cursor:
            constraints = connection.introspection.get_constraints(cursor, table)
        constraint = constraints.get(diagnostic.constraint_name, {})
        return bool(constraint.get('unique') and not constraint.get('primary_key') and
                    set(constraint.get('columns', ())) == set(columns))
    return False
