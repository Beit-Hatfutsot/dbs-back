import pymssql
from maya import MayaDT, now

class MigrationSQLClient:
    def __init__(self, server, user, password, db, max_recursive_calls=2,
                 debug=False):
        self.connection = pymssql.connect(server, user, password, db,
            as_dict=True, login_timeout=10)

        self.connection._conn.debug_queries = debug
        self.cursor = self.connection.cursor()
        self.recursive_calls = 0
        self.max_recursive_calls = max_recursive_calls

    def execute(self, query, hunk_size=10000, stringify=False, 
                unit_ids=None, since=0, until=0):
        """ This method executes a SQL query and returns a pymssql cursor """

        params = {}
        if unit_ids:
            params['unit_ids'] = [i for i in unit_ids if i]
            since = until = 0
        else:
            params['unit_ids'] = [0]
        params['since'] = MayaDT(since).datetime().strftime('%Y-%m-%d %H:%M:%S')
        params['until'] = MayaDT(until).datetime().strftime('%Y-%m-%d %H:%M:%S')
        self.cursor.execute(query, params)
        return self.cursor

    def audit(self, **params):
        self.cursor.execute(params['query'], (params['operation'], params['from_date'], params['to_date'], params['unit_type']))
        return self.cursor

    def close_connections(self):
        self.cursor.close()
        self.connection.close()
