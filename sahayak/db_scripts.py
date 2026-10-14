"""Execute trusted repository SQL scripts in the caller's existing transaction."""

def execute_script(connection, script: str):
    # psycopg treats literal percent signs as placeholders when passed even an
    # empty parameter mapping. Repository DDL contains %ROWTYPE and LIKE '%...%'.
    # Omit parameters entirely; never use this helper for interpolated user input.
    with connection.connection.driver_connection.cursor() as cursor:
        cursor.execute(script)
