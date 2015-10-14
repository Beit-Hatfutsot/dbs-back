#!/usr/bin/env python

import json

from pprint import pprint


def invert_related_vector(vector_dict):
    rv = []
    key = vector_dict.keys()[0]
    for value in vector_dict.values()[0]:
        rv.append({value: [key]})
    return rv

def reverse_related(direct_related):
    rv = []
    for vector in direct_related:
        for r in invert_related_vector(vector):
            rv.append(r)

    return rv

def reduce_related(related_list):
    reduced = {}
    for r in related_list:
        key = r.keys()[0]
        value = r.values()[0]
        if key in reduced:
            reduced[key].extend(value)
        else:
            reduced[key] = value

    rv = []
    for key in reduced:
        rv.append({key: reduced[key]})
    return rv

def unify_related_lists(l1, l2):
    rv = l1[:]
    rv.extend(l2)
    return reduce_related(rv)

def lists_have_same_content(l1, l2):
    for d1, d2 in zip(sorted(l1), sorted(l2)):
        if not dicts_have_same_content(d1, d2):
            return False
    return True

def dicts_have_same_content(d1, d2):
    for key in d1.keys():
        if not sorted(d1[key]) == sorted(d2[key]):
            return False
    return True

if __name__ == '__main__':

    outgoing_related = [{'places.1': ['photos.1','personalities.2']},
                        {'photos.1': ['places.1', 'photos.3']},
                        {'personalities.4': ['photos.5', 'photos.1']}]

    not_reduced = reverse_related(outgoing_related)
    unified = unify_related_lists(outgoing_related, not_reduced)



