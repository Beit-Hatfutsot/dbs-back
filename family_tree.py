from py2neo import Graph, Node, Relationship

def fwalk(individual_id, tree_number, radius=3):
    graph = Graph('http://{}:{}@{}:{}/db/data/'.format(
                    args.user[0], args.user[1],
                    args.host, args.port,
    ))
    w = graph.cypher.execute("""

                             """)

