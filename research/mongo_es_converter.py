def get_array_members(array):
    for m in array:
        if type(m) != dict:
            return array
        else:
            field = m.keys()[0]
            print field
            return get_array_members(m]field])

example_array = [{'UnitText1.En': {'$nin': [None, '']}}, {'UnitText1.He': {'$nin': [None, '']}}]


