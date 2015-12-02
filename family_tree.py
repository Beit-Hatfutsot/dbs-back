def fwalk(graph, individual_id, radius=1, nodes={}):
    tx = graph.cypher.begin()
    tx.append("""
        MATCH (n)
        WHERE ID(n)={}
        RETURN n
    """.format(individual_id))
    # parents
    tx.append("""
        MATCH (n)<-[:FATHER_OF|:MOTHER_OF]-(r)
        WHERE ID(n)={}
        RETURN ID(r)
    """.format(individual_id))
    # spouses
    tx.append("""
        MATCH (n)-[:SPOUSE]-(r)
        WHERE ID(n)={}
        RETURN ID(r)
    """.format(individual_id))
    # siblings
    tx.append("""
        MATCH (n)<-[:FATHER_OF|:MOTHER_OF]-(p)-[:FATHER_OF|:MOTHER_OF]->(r)
        WHERE ID(n)={}
        RETURN DISTINCT ID(r)
    """.format(individual_id))
    # children
    tx.append("""
        MATCH (n)-[:FATHER_OF|:MOTHER_OF]->(r)
        WHERE ID(n)={}
        RETURN ID(r)
    """.format(individual_id))
    # need to add the data from the r: n.r is an array of Rellationships
    results = tx.commit()
    n = results[0][0].n.properties
    nodes = {individual_id: n}
    n['parents'] = parse_results(graph, nodes, results[1], radius)
    n['spouses'] = parse_results(graph, nodes, results[2], radius)
    n['sibilings'] = parse_results(graph, nodes, results[3], radius)
    n['children'] = parse_results(graph, nodes, results[4], radius)
    return nodes

def parse_results(graph, nodes, results, radius):
    ret = []
    for i in results:
        ret.append(i[0])
        if radius > 0 and i[0] not in nodes:
            nodes.update(fwalk(graph, i[0], radius-1, nodes))
    return ret

