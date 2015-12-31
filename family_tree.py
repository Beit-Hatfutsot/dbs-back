from copy import copy

class People(dict):

    def add_node(this, node):
        props = node.properties
        pid = props['id'][1:-1]
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


def fwalk(graph, tree_number, node_id):
    # Add opening and closing `#` if missing
    if node_id != '@':
        node_id = '@'+ node_id
    if node_id[-1] != '@':
        node_id = node_id + '@'

    results = graph.cypher.execute("".join((
        "MATCH (t:Tree {tree_number: {t}})<-[:LEAF_IN]-(n:INDI {id: {i}})",
        "-[r:FATHER_OF|:MOTHER_OF|:SPOUSE*1..3]-(o:INDI) ",
        "RETURN n, r")), t=int(tree_number), i=node_id)

    # need to add the data from the r: n.r is an array of Rellationships
    people = People()
    try:
        p = people.add_node(results[0].n)
        p_id = p['props']['id']
    except IndexError:
        raise AttributeError("Failed to find the person you're looking for. Sorry")

    for i in results:
        for rel in i.r:
            src = people.add_node(rel.nodes[0])
            dst = people.add_node(rel.nodes[1])
            if rel.type == 'FATHER_OF' or rel.type == 'MOTHER_OF':
                src['children'].add(dst['props']['id'])
                dst['parents'].add(src['props']['id'])
            else:
                src['partners'].add(dst['props']['id'])
                dst['partners'].add(src['props']['id'])

    # collect the siblings
    for id, n in people.items():
        if id != p_id and p['parents'].intersection(n['parents']):
            p['siblings'].add(id)
            n['siblings'].add(p_id)

    # gather grandchildren and other parent
    for i in p['children']:
        child = people[i]
        for j in child['children']:
            grandchild = people[j]
            grandchild['props']['parents'] = people.get_props_array(
                grandchild['parents'], shallow_copy=True)
        child['props']['children'] = people.get_props_array(child['children'],
                                                            shallow_copy=True)
        child['props']['parents'] = people.get_props_array(child['parents'],
                                                            shallow_copy=True)
        child['props']['partners'] = people.get_props_array(child['partners'],
                                                            shallow_copy=True)

    # gather grandparents and ~siblings
    for i in p['parents']:
        parent = people[i]
        parent['props']['parents'] = people.get_props_array(parent['parents'],
                                                            shallow_copy=True)
        parent['props']['partners'] = people.get_props_array(parent['partners'],
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
    for k,v in results[0].n.properties.items():
        p[k.lower()] = v
    p['id'] = p_id
    del p['props']
    return p


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

