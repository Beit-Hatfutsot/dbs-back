import elasticsearch
import pprint

def get_array_members(array):
    for m in array:
        if type(m) != dict:
            return array
        else:
            field = m.keys()[0]
            print field
            return get_array_members(m[field])

example_array = [{'UnitText1.En': {'$nin': [None, '']}}, {'UnitText1.He': {'$nin': [None, '']}}]

es = elasticsearch.Elasticsearch('localhost')

search_string = 'Albert Einstein'

es_query_filter =  {
                    'or': {
                        'filters': [
                            {
                                'and': {
                                    'filters': [
                                        {'not':
                                            {'filter':
                                                {'term':
                                                    {'UnitText1.En': None}
                                                }
                                            }
                                        },
                                        {'not':
                                            {'filter':
                                                {'term':
                                                    {'UnitText1.En': ''}
                                                }
                                            }
                                        }
                                    ]
                                }
                            },
                            {
                                'and': {
                                    'filters': [
                                        {'not':
                                            {'filter':
                                                {'term':
                                                    {'UnitText1.He': None}
                                                }
                                            }
                                        },
                                        {'not':
                                            {'filter':
                                                {'term':
                                                    {'UnitText1.He': ''}
                                                }
                                            }
                                        }
                                    ]
                                }
                            }
                        ]
                    }
                }

simple_filter = {
                'not': {
                    'term': {
                        'UnitText1.En': None
                    }
                }
            }

es_filtered_query = {
    'query': {
        'filtered' : {
            'query' : {
                'match' : { '_all' : search_string }
            },
            'filter': es_query_filter
        }
    }
}

es_filtered_query = {
    'query': {
        'filtered' : {
            'query' : {
                'match' : { '_all' : search_string }
            },
            #'filter': es_query_filter
            'filter': simple_filter
        }
    }
}
try:
    res = es.search(body=es_filtered_query)
    pprint.pprint(res)
except elasticsearch.exceptions.RequestError as e:
    print dir(e)
    pprint.pprint(e.info['error'])
