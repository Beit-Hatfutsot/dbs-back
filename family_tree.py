from py2neo import Graph, Node, Relationship

def fwalk(neo4j_url, individual_id, tree_id, radius=3):
    graph = Graph(neo4j_url)
    neighbours = graph.cypher.execute("""
    MATCH (:Person {{id: '{}', tree_id: '{}' }})-[r*1..{}]-(p:Person)
    RETURN p, r
    """.format(individual_id, tree_id, radius))
    # need to add the data from the r: n.r is an array of Rellationships
    return map(lambda n: n.p.properties, neighbours)

