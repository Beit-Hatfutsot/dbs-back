#!/usr/bin/env python
import argparse

import pymongo
from bson.code import Code

from bhs_api import create_app


def parse_args():
    parser = argparse.ArgumentParser(description= 'compare the trees')
    parser.add_argument('--fromdb',
                        help='the db from which to copy the slugs')
    return parser.parse_args()


if __name__ == '__main__':
    args = parse_args()
    app, conf = create_app()
    fromdb = app.client_data_db[args.fromdb]
    trees = app.data_db.trees

    # TODO: remove references to the genTreeIndividuals collection - it is irrelevant and not in use
    # '''
    # old_trees = fromdb.genTreeIndividuals.map_reduce(
    #     Code("function() {emit (this.GTN, this.tree.meta.num_nodes)}"),
    #     Code("function(k, vs) {return vs[0]}"),
    #     "treeSizes",
    # query = {'tree': {'$exists': True}})
    #
    # '''
    old_trees = list(fromdb.treeSizes.find())

    to_mig = []
    for old_tree in old_trees:
        num = old_tree['_id']
        old_size = old_tree["value"]
    	new_tree = trees.find_one({'num': num})
        if not new_tree:
            to_mig.append(num)
            continue
	new_size = new_tree['versions'][-1]['persons']
	if new_size < old_size:
            to_mig.append(num)
    for i in to_mig:
        print "python scripts/migrate.py -t " + str(i)
    to_mig = ','.join(map(str, to_mig))
    f=open("drop_trees.js","w")
    f.write("use {};".format(app.conf.data_db_name))
    f.write("db.trees.remove({{num: {{'$in': [{}]}}}});".format(to_mig))
    f.write("db.persons.remove({{tree_num: {{'$in': [{}]}}}});".format(to_mig))
    f.close()
    
