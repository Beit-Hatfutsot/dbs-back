import pytest
from py2neo import Graph, Node, Relationship
from pytest_flask.plugin import client

from family_tree import fwalk
from api import conf

def delete_test_graph(g):
    g.cypher.execute("MATCH (n:Tree {test: true})\
                        OPTIONAL MATCH n-[r]-() DELETE r,n")
    g.cypher.execute("MATCH (n:INDI {test: true})\
                        OPTIONAL MATCH n-[r]-() DELETE r,n")
@pytest.fixture
def simple_family(request):
    ''' a fixture to add a simple family tree
                    +-----------------+
                    |great grandfather|
                    +-----------------+
                    FATHER_OF|
                        +-----v-----+               +-----------+
                        |grandfather+-----spouse----+grandmother|
                        +-----+-----+               +-----+-----+
                              +----------+        +-------+
                                FATHER_OF|        |MOTHER_OF
                            +-----------++--------+-----+
                            |           |               |
        +------+        +-----v+       +--v--+         +--v-+
        |father+---S----+mother|       |uncle|         |aunt|
        +--+---+        +---+--+       +-----+         +----+
           +-----+    +-----+
        FATHER_OF|    |MOTHER_OF
        +-------------+-----------+
        |             |           |
    +---v----+   +----v---+    +--v---+
    |brother1|   |brother2|    |sister|
    +--------+   +--------+    +------+

    '''

    g = Graph(conf.neo4j_url)

    request.addfinalizer(lambda: delete_test_graph(g))
    t = Node("Tree", test=True, tree_number=1, id='@1@')
    nodes = [
        Node("INDI", test=True, id='@1@', NAME="grandfather's father", SEX='M'),
        Node("INDI", test=True, id='@2@', NAME="grandfather", SEX='M'),
        Node("INDI", test=True, id='@3@', NAME="grandmother", SEX='F'),
        Node("INDI", test=True,id='@4@', NAME="mother", SEX='F', birth_year=1940),
        Node("INDI", test=True,id='@5@', NAME="father", SEX='M'),
        Node("INDI", test=True,id='@6@', NAME="uncle", SEX='M'),
        Node("INDI", test=True,id='@7@', NAME="aunt", SEX='F'),
        Node("INDI", test=True,id='@8@', NAME="brother1", SEX='M', birth_year=1965),
        Node("INDI", test=True,id='@9@', NAME="brother2", SEX='M', birth_year=1963),
        Node("INDI", test=True,id='@10@', NAME="sister", SEX='F', birth_year=1964),
        Node("INDI", test=True,id='@11@', SEX='F'),
    ]

    rels = [ Relationship(nodes[0], "FATHER_OF", nodes[1]),
             Relationship(nodes[1], "FATHER_OF", nodes[3]),
             Relationship(nodes[1], "FATHER_OF", nodes[5]),
             Relationship(nodes[1], "FATHER_OF", nodes[6]),
             Relationship(nodes[1], "SPOUSE", nodes[0]),
             Relationship(nodes[2], "MOTHER_OF", nodes[3]),
             Relationship(nodes[2], "MOTHER_OF", nodes[5]),
             Relationship(nodes[2], "MOTHER_OF", nodes[6]),
             Relationship(nodes[4], "FATHER_OF", nodes[7]),
             Relationship(nodes[4], "FATHER_OF", nodes[8]),
             Relationship(nodes[4], "FATHER_OF", nodes[9]),
             Relationship(nodes[4], "FATHER_OF", nodes[10]),
             Relationship(nodes[3], "SPOUSE", nodes[4]),
             Relationship(nodes[3], "MOTHER_OF", nodes[7]),
             Relationship(nodes[3], "MOTHER_OF", nodes[8]),
             Relationship(nodes[3], "MOTHER_OF", nodes[9]),
             Relationship(nodes[3], "MOTHER_OF", nodes[10]),
            ]
    for i in nodes:
        rels.append(Relationship(i, "LEAF_IN", t))
    nodes.append(t)
    g.create(*nodes)
    g.create(*rels)
    g.cypher.execute("CREATE INDEX ON :INDI(test)")
    g.cypher.execute("CREATE INDEX ON :Tree(test)")
    return g, nodes

@pytest.fixture
def complex_family(request):
    ''' a fixture to add a complex family tree

    +------+          +-----------+          +-----+          +-------+
    |Rivka +-+SPOUSE+-+    Elo    +-+SPOUSE+-+Giza +-+SPOUSE+-+Volvek |
    +---+--+          +-----+-----+          +--+--+          +-------+
        |                   |                   |                 |
        +----------+        |      +-------------------------+    |
        |          |        |      |            |            |    |
    +---------------+------+----+------------+  |            |    |
    |  |          | |           | |          |  |            |    |
    +-+--+-+      +-+-+---+     +-+-+---+     ++-+----+      ++----++
    |Nurit |      |Miriam |     |Lea    |     |Rachel |      |Hayuta|
    +------+      +-------+     +-------+     +---+---+      +------+
                                                |
                                +--------------+
        +--------+          +--------+          +------+
        |Shlomi  +-+SPOUSE+-+Michal  +-+SPOUSE+-+Yossi |
        +---+----+          +---+----+          +---+--+
            |                   |                   |
            |                   |                   |
            |    +---------+    |      +-------+    |
            +----+Yehonatan+----+------+Adi    +----+
                 +---------+           +-------+


    '''

    g = Graph(conf.neo4j_url)
    request.addfinalizer(lambda: delete_test_graph(g))
    t = Node("Tree", test=True, tree_number=2, id='@1@')
    nodes = [
        Node("INDI", test=True, id='@1@', NAME="Rivka", SEX='F'),
        Node("INDI", test=True, id='@2@', NAME="Elo", SEX='M'),
        Node("INDI", test=True, id='@3@', NAME="Giza", SEX='F'),
        Node("INDI", test=True, id='@4@', NAME="Volvek", SEX='M'),
        Node("INDI", test=True, id='@5@', NAME="Nurit", SEX='F'),
        Node("INDI", test=True, id='@6@', NAME="Miriam", SEX='F'),
        Node("INDI", test=True, id='@7@', NAME="Lea", SEX='F'),
        Node("INDI", test=True, id='@8@', NAME="Rachel", SEX='F'),
        Node("INDI", test=True, id='@9@', NAME="Hayuta", SEX='F'),
        Node("INDI", test=True, id='@10@', NAME="Michal", SEX='F'),
        Node("INDI", test=True, id='@11@', NAME="Yossi", SEX='M'),
        Node("INDI", test=True, id='@12@', NAME="Shlomi", SEX='M'),
        Node("INDI", test=True, id='@13@', NAME="Adi", SEX='F'),
        Node("INDI", test=True, id='@14@', NAME="Yehonatan", SEX='M'),
    ]

    rels = [ Relationship(nodes[0], "MOTHER_OF", nodes[4]),
             Relationship(nodes[0], "MOTHER_OF", nodes[5]),
             Relationship(nodes[1], "FATHER_OF", nodes[4]),
             Relationship(nodes[1], "FATHER_OF", nodes[5]),
             Relationship(nodes[1], "FATHER_OF", nodes[6]),
             Relationship(nodes[1], "FATHER_OF", nodes[7]),
             Relationship(nodes[2], "MOTHER_OF", nodes[6]),
             Relationship(nodes[2], "MOTHER_OF", nodes[7]),
             Relationship(nodes[2], "MOTHER_OF", nodes[8]),
             Relationship(nodes[3], "FATHER_OF", nodes[8]),
             Relationship(nodes[0], "SPOUSE", nodes[1]),
             Relationship(nodes[1], "SPOUSE", nodes[2]),
             Relationship(nodes[2], "SPOUSE", nodes[3]),
             Relationship(nodes[7], "MOTHER_OF", nodes[9]),
             Relationship(nodes[9], "SPOUSE", nodes[10]),
             Relationship(nodes[9], "SPOUSE", nodes[11]),
             Relationship(nodes[9], "MOTHER_OF", nodes[12]),
             Relationship(nodes[9], "MOTHER_OF", nodes[13]),
             Relationship(nodes[10], "FATHER_OF", nodes[12]),
             Relationship(nodes[11], "FATHER_OF", nodes[13]),
            ]
    for i in nodes:
        rels.append(Relationship(i, "LEAF_IN", t))
    nodes.append(t)
    g.create(*nodes)
    g.create(*rels)
    return g, nodes

def test_walk(simple_family):

    g, nodes = simple_family
    just_name = lambda a: a.get('name', 'unknown')
    # get the data for our mother
    mother = fwalk(g, tree_number=1, node_id="4")
    assert mother['name'] == 'mother'
    assert mother['birth_year'] == 1940
    parents = set(map(just_name, mother['parents']))
    assert parents == set(['grandmother', 'grandfather'])
    children = map(just_name, mother['children'])
    assert children == ['brother2', 'sister', 'brother1', '']
    partners = set(map(just_name, mother['partners']))
    assert partners == set(['father'])
    siblings = set(map(just_name, mother['siblings']))
    assert siblings == set(['uncle', 'aunt'])
    # now test that great grandfather is there
    for p in mother['parents']:
        if p['name'] == 'grandfather':
            greatgrandfathers = set(map(just_name, p['parents']))
            assert greatgrandfathers == set(["grandfather's father"])
    # test that all the children have a father
    for i in mother['children']:
        assert set(map(just_name, i['parents'])) == set(['father', 'mother'])


def test_walk_api(simple_family, client):
    r = client.get('/fwalk/1/4')
    mother = r.json
    assert len(mother.keys()) == 10


def test_unknown_id(simple_family, client):
    r = client.get('/fwalk/10/10800')
    assert r.status_code == 400

def test_half_sisters(complex_family):
    g, nodes = complex_family
    just_name = lambda a: a.get('name', 'unknown')
    # first get the id of our mother
    id = nodes[7].ref[5:]
    rachel = fwalk(g, tree_number=2, node_id="8")
    siblings = set(map(just_name, rachel['siblings']))
    assert siblings == set(['Lea', 'Hayuta', 'Miriam', 'Nurit'])
    for i in rachel['siblings']:
        p = set(map(just_name, i['parents']))
        if i['name'] == 'Lea':
            assert p == set(['Giza', 'Elo'])
        if i['name'] == 'Hayute':
            assert p == set(['Giza', 'Volvek'])
        if i['name'] == 'Miriam' or i['name'] == 'Nurit':
            assert p == set(['Elo', 'Rivka'])
    parents = set(map(just_name, rachel['parents']))
    assert parents == set(['Giza', 'Elo'])
    for i in rachel['parents']:
        c = set(map(just_name, i['children']))
        p = set(map(just_name, i['partners']))
        if i['name'] == 'Giza':
            assert c == set(['Rachel', 'Lea', 'Hayuta'])
            assert p == set(['Elo', 'Volvek'])
        if i['name'] == 'Elo':
            assert c == set(['Miriam', 'Nurit', 'Rachel', 'Lea'])
            assert p == set(['Giza', 'Rivka'])
    assert map(just_name, rachel['children']) == ['Michal']
    michal = rachel['children'][0]
    p = set(map(just_name, michal['partners']))
    assert p == set(['Shlomi', 'Yossi'])
    adi = michal['children'][0]
    assert adi['name'] == 'Adi'
    assert set(map(just_name,adi['parents'])) == set(['Yossi','Michal'])
