import pymssql
from maya import MayaDT, now

class MigrationSQLClient:
    def __init__(self, server, user, password, db, max_recursive_calls=2):
        self.connection = pymssql.connect(server, user, password, db,
            as_dict=True, login_timeout=10)
        
        self.connection._conn.debug_queries= True
        self.cursor = self.connection.cursor()
        self.recursive_calls = 0
        self.max_recursive_calls = max_recursive_calls

    def execute(self, query, hunk_size=10000, stringify=False, 
                unit_id=0, since=0, until=0):
        """ This method executes a SQL query and returns a pymssql cursor """

        params = {'unit_id': unit_id}
        params['since'] = MayaDT(since).iso8601() if since else 0
        params['until'] = MayaDT(until).iso8601() if until else now().iso8601()
        self.cursor.execute(query, params)
        return self.cursor

    def audit(self, **params):
        self.cursor.execute(params['query'], (params['operation'], params['from_date'], params['to_date'], params['unit_type']))
        return self.cursor

    def close_connections(self):
        self.cursor.close()
        self.connection.close()
