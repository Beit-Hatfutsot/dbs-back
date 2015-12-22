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
            person = {'children': set(), 'parents': set(),
                      'partners': set(), 'siblings': set(),
                      'order': {'birth_year': props.get('birth_year', 9999),
                                'marriage_year': props.get('birth_year', 9999),
                               },
                      'props': {'sex':props.get('SEX', 'U'),
                                'name':name,
                                'id':pid,
                               },
                      }
            this[pid] = person
        return this[pid]

    def get_props_array(self, ids, shallow_copy=False, order_by_parents=False):
        ''' gets an array of `ids` and return a sorted array where each cell
            holds the `props` of the element.
            There's an optional switch - `shallow_copy` that tells whether
            to copy the props.
        '''
        def get_props(id):
            props = self[id]['props']
            if shallow_copy:
                props = copy(props)
            return props

        def order(x, y):
            px = self[x]
            py = self[y]
            ret = 0
            if order_by_parents:
                ret = cmp(sorted(list(px['parents'])),
                          sorted(list(py['parents'])))
            return ret or \
                   cmp(px['order']['birth_year'], py['order']['birth_year']) or \
                   cmp(px['props']['name'], py['props']['name'])

        sorted_ids = sorted(ids, order)
        return map(get_props, sorted_ids)


def fwalk(graph, args):
    tx = graph.cypher.begin()
    if "t" in args and "i" in args:
        i = args["i"]
        # Add opening and closing `#` if missing
        if i[0] != '@':
            i = '@'+ i
        if i[-1] != '@':
            i = i + '@'
        where_clause = "WHERE n.tree_id='{}' AND n.id='{}'".format(args["t"], i)
    elif "i" in args:
        where_clause = "WHERE ID(n)={}".format(args["i"])
    else:
        raise AttributeError("I need either an i and an optional to find a person")

    tx.append(" ".join((
        "MATCH (n:INDI)",
        where_clause,
        "RETURN n, ID(n)")))
    tx.append(" ".join((
        "MATCH (n:INDI)<-[r:FATHER_OF|:MOTHER_OF*1..2]-(parents:INDI)",
        where_clause,
        "RETURN parents, r")))
    tx.append(" ".join((
        "MATCH (n:INDI)-[:SPOUSE]-(spouses:INDI)",
        where_clause,
        "RETURN spouses")))
    # siblings
    tx.append(" ".join((
        "MATCH (n:INDI)<-[:FATHER_OF|:MOTHER_OF]-(p1:INDI)-[:FATHER_OF|:MOTHER_OF]->(siblings:INDI)",
        where_clause,
        "OPTIONAL MATCH (p2)-[:FATHER_OF|:MOTHER_OF]->(siblings)",
        "RETURN siblings, p1, p2")))
    # children
    tx.append(" ".join((
        "MATCH (n:INDI)-[r:FATHER_OF|:MOTHER_OF*1..2]->(children)",
        where_clause,
        "OPTIONAL MATCH (children)<-[:FATHER_OF|:MOTHER_OF]-(p:INDI)",
        "WHERE p <> n",
        "RETURN children, r, p")))
    # need to add the data from the r: n.r is an array of Rellationships
    results = tx.commit()
    people = People()
    try:
        p = people.add_node(results[0][0].n)
    except IndexError:
        raise AttributeError("Failed to find the person you're looking for. Sorry")

    parse_ver(graph, people, results[1])
    parse_ver(graph, people, results[4])
    p['partners'] = parse_hor(graph, people, results[2])
    p['siblings'] = parse_hor(graph, people, results[3])

    # gather grandchildren and other parent
    for i in p['children']:
        child = people[i]
        child['props']['children'] = people.get_props_array(child['children'],
                                                            shallow_copy=True)
        child['props']['parents'] = people.get_props_array(child['parents'],
                                                            shallow_copy=True)

    # gather grandparents and ~siblings
    for i in p['parents']:
        parent = people[i]
        parent['props']['parents'] = people.get_props_array(parent['parents'],
                                                            shallow_copy=True)
        parent['props']['children'] = people.get_props_array(parent['children'],
                                                            shallow_copy=True)

    # gather step parents
    for i in p['siblings']:
        sibling = people[i]
        sibling['props']['parents'] = people.get_props_array(sibling['parents'],
                                                            shallow_copy=True)

    p['children'] = people.get_props_array(p['children'], order_by_parents=True)
    p['partners'] = people.get_props_array(p['partners'])
    p['parents'] = people.get_props_array(p['parents'])
    p['siblings'] = people.get_props_array(p['siblings'], order_by_parents=True)
    # copy all the properties from the node but keep all the keys lower case
    for k,v in results[0][0].n.properties.items():
        p[k.lower()] = v
    p['id'] = str(results[0][0][1])
    del p['props']
    return p

def parse_ver(graph, people, results):
    for i in results:
        for rel in i[1]:
            src = people.add_node(rel.nodes[0])
            dst = people.add_node(rel.nodes[1])
            if rel.type == 'FATHER_OF' or rel.type=='MOTHER_OF':
                src['children'].add(dst['props']['id'])
                dst['parents'].add(src['props']['id'])
            else:
                assert False
        # for children we add parents
        if len(i) > 2 and i[2]:
            child = people.add_node(i[0])
            parent = people.add_node(i[2])
            child['parents'].add(parent['props']['id'])

def parse_hor(graph, people, results):
    ret = set()
    for i in results:
        person = people.add_node(i[0])
        for j in range(1, len(i)):
            parent = people.add_node(i[j])
            person['parents'].add(parent['props']['id'])
            parent['children'].add(person['props']['id'])
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

