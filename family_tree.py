from copy import copy

get_node_id = lambda node: node.ref[5:]

class People(dict):

    def add_node(this, node):
        pid = get_node_id(node)
        props = node.properties
        if pid not in this:
            try:
                name = nameof(props['NAME'])
            except KeyError:
                name = ''
            person = {'children':set(), 'parents':set(),
                        'partners':set(), 'siblings':set(),
                        'active_partner':None,
                        'props':{'sex':props.get('SEX', 'U'),
                                'name':name,
                                'id':pid}}
            this[pid] = person
        return this[pid]


def fwalk(graph, individual_id):
    tx = graph.cypher.begin()
    tx.append("""
              MATCH (n)
              WHERE ID(n)={}
              RETURN n
              """.format(individual_id))
    tx.append("""
              MATCH (n)<-[r:FATHER_OF|:MOTHER_OF*1..2]-(parents:INDI)
              WHERE ID(n)={}
              RETURN parents, r
              """.format(individual_id))
    tx.append("""
              MATCH (n)-[:SPOUSE]-(spouses:INDI)
              WHERE ID(n)={}
              RETURN spouses
              """.format(individual_id))
    # siblings
    tx.append("""
              MATCH (n)<-[:FATHER_OF|:MOTHER_OF]-(p:INDI)-[:FATHER_OF|:MOTHER_OF]->(siblings:INDI)
              WHERE ID(n)={}
              RETURN siblings
              """.format(individual_id))
    # children
    tx.append("""
              MATCH (n)-[r:FATHER_OF|:MOTHER_OF*1..2]->(children)
              WHERE ID(n)={}
              RETURN children, r
              """.format(individual_id))
    # need to add the data from the r: n.r is an array of Rellationships
    results = tx.commit()
    people = People()
    p = people.add_node(results[0][0].n)
    parse_ver(graph, people, results[1])
    parse_ver(graph, people, results[4])
    p['partners'] = parse_hor(graph, people, results[2])
    p['siblings'] = parse_hor(graph, people, results[3])


    # gather grandchildren
    for i in p['children']:
        child = people[i]
        child['props']['children'] = [copy(people[x]['props'])
                                      for x in child['children']]
    # gather grandparents
    for i in p['parents']:
        parent = people[i]
        parent['props']['parents'] = [copy(people[x]['props'])
                                     for x in parent['parents']]

    p['children'] = [people[x]['props'] for x in p['children']]
    p['partners'] = [people[x]['props'] for x in p['partners']]
    p['parents'] = [people[x]['props'] for x in p['parents']]
    p['siblings'] = [people[x]['props'] for x in p['siblings']]
    # copy all the properties from the node but keep all the keys lower case
    for k,v in results[0][0].n.properties.items():
        p[k.lower()] = v
    p['id'] = individual_id
    del p['props']
    return p

def parse_ver(graph, people, results):
    for i in results:
        for rel in i[1]:
            for n in rel.nodes:
                people.add_node(n)
            src = people.add_node(rel.nodes[0])
            dst = people.add_node(rel.nodes[1])
            if rel.type == 'FATHER_OF' or rel.type=='MOTHER_OF':
                src['children'].add(dst['props']['id'])
                dst['parents'].add(src['props']['id'])
            else:
                assert False


def parse_hor(graph, people, results):
    ret = set()
    for i in results:
        person = people.add_node(i[0])
        ret.add(person['props']['id'])
    return ret


def nameof(name):
    if not name:
        return ''
    parts = [x.strip() for x in name.split('/')]
    if "," in parts[0]:
        parts[0] = parts[0].split(",")
        parts[0 ] = parts[0][0]+" (%s)" % "/".join(parts[0][1:])
    try:
        parts = [ parts[2], parts[0], parts[1] ]
    except IndexError:
        return name

    parts = [p for p in parts if p != '']
    return " ".join(parts)

