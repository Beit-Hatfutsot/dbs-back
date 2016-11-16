import pymssql

class MigrationSQLClient:
    def __init__(self, server, user, password, db, max_recursive_calls=2):
        self.connection = pymssql.connect(server, user, password, db, as_dict=True, login_timeout=10)
        self.cursor = self.connection.cursor()
        self.recursive_calls = 0
        self.max_recursive_calls = max_recursive_calls

    def execute(self, query, select_ids=False, unit_ids=[], chunk_size=10000, stringify=False):
        """
        This method executes a SQL query with a list of unit ids as a parameter to the query.
        returns: 
        pymssql cursor if select_ids is False, or if select_ids is True and the unit_ids list is not to big for MSSQL to handle.
        In case the unit_ids list is to big, the method goes into recursive execution with two halves of the list,
        and returns a list instead of a cursor.  
        In case slect_ids is True and the unit ids list is empty the return value is None.

        The unit ids will be wrapped in "'" if stingify is set to True (to accomodate uniqueidentifier values in TSQL).
        """

        if select_ids and len(unit_ids) > 0:
            # remove all empty strings from unit_ids
            unit_ids = [i for i in unit_ids if i != '']

            if len(unit_ids) is 1:
                self.cursor.execute(query, (1, unit_ids[0]))
            else:
                # replace %s with a string of comma seperated ids,
                # since we cn't pass a tuple to the query
                try:
                    index = query.rindex('%s')
                except ValueError:
                    import pdb; pdb.set_trace()
                query_string = query

                if stringify:
                    unit_ids = ["'" + str(unit_id) + "'" for unit_id in unit_ids]
                id_string = ','.join([str(i) for i in unit_ids])
                query_string = query_string[:index] + id_string + query_string[index+2:]
                
                try:
                    self.cursor.execute(query_string, (1))
                except pymssql.OperationalError as e:
                    if e.args[0] == 8623:
                        # result_list = []
                        # unit_ids_chunks = [unit_ids[i:i+chunk_size] for i in xrange(0, len(unit_ids), chunk_size)]
                        # for id_chunk in unit_ids_chunks:
                        #     chunk_cursor = self.execute(query, select_ids=True, unit_ids=id_chunk)
                        #     result_list.extend(list(chunk_cursor))
                        # return result_list

                        self.recursive_calls = self.recursive_calls + 1
                        if self.recursive_calls > self.max_recursive_calls:
                            print 'Too many recursive SQL query executions'
                            exit(1)
                        unit_ids1 = unit_ids[:len(unit_ids)/2]
                        unit_ids2 = unit_ids[len(unit_ids)/2:]
                        cursor1 = self.execute(query, select_ids=True, unit_ids=unit_ids1)
                        list1 = list(cursor1)
                        cursor2 = self.execute(query, select_ids=True, unit_ids=unit_ids2)
                        list2 = list(cursor2)
                        cursor1.close()
                        cursor2.close()
                        return list1 + list2
                    else:
                        raise e
        elif select_ids and len(unit_ids) == 0:
            return None
        else:
            self.cursor.execute(query, (0, ''))

        return self.cursor

    def audit(self, **params):
        self.cursor.execute(params['query'], (params['operation'], params['from_date'], params['to_date'], params['unit_type']))
        return self.cursor

    def close_connections(self):
        self.cursor.close()
        self.connection.close()
