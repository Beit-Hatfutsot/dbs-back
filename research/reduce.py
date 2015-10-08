#!/usr/bin/env python


def invert_related_vector(vector_dict):
    rv = []
    key = vector_dict.keys()[0]
    for value in vector_dict.values()[0]:
        rv.append({value: [key]})
    return rv

def reduce_related(related):
    reduced = {}
    for vector in related:
        for r in invert_related_vector(vector):
            key = r.keys()[0]
            value = r.values()[0]
            if key in reduced:
                reduced[key].extend(value)
            else:
                reduced[key] = value
    return reduced

if __name__ == '__main__':

    outgoing_related = [{'places.1': ['photos.1','personalities.2']},
                        {'photos.1': ['places.1', 'photos.3']},
                        {'personalities.4': ['photos.5', 'photos.1']}]

    db = [{'places': [{'_id': 1, 'related': []}, {'_id': 2, 'related': []}]},
    {'photos': [{'_id': 1, 'related': []}, {'_id': 2, 'related': []}, {'_id': 3, 'related': []}, {'_id': 5, 'related': []}]},
    {'personalities': [{'_id': 1, 'related': []}, {'_id': 2, 'related': []}, {'_id': 4, 'related': []}]}]

    print 'Direct:', outgoing_related
    print 'Inverted:', reduce_related(outgoing_related)
