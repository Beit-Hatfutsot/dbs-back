import pytest
from py2neo import Graph, Node, Relationship
from pytest_flask.plugin import client

from family_tree import fwalk
from api import conf

@pytest.fixture
def graph(request):
    ''' a fixture to add a simple family tree graph
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
    def fin():
        g.cypher.execute("MATCH (n { tree_id: '1' }) optional match (n)-[r]-() delete n,r")
    request.addfinalizer(fin)

    g = Graph(conf.neo4j_url)
    nodes = [
        Node("INDI", tree_id='1', id='1', NAME="grandfather's father", SEX='M'),
        Node("INDI", tree_id='1', id='2', NAME="grandfather", SEX='M'),
        Node("INDI", tree_id='1', id='3', NAME="grandmother", SEX='F'),
        Node("INDI", tree_id='1', id='4', NAME="mother", SEX='F', birth_year=1940),
        Node("INDI", tree_id='1', id='5', NAME="father", SEX='M'),
        Node("INDI", tree_id='1', id='6', NAME="uncle", SEX='M'),
        Node("INDI", tree_id='1', id='7', NAME="aunt", SEX='F'),
        Node("INDI", tree_id='1', id='8', NAME="brother1", SEX='M', birth_year=1965),
        Node("INDI", tree_id='1', id='9', NAME="brother2", SEX='M', birth_year=1963),
        Node("INDI", tree_id='1', id='10', NAME="sister", SEX='F', birth_year=1964),
        Node("INDI", tree_id='1', id='11', SEX='F'),
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
    g.create(*nodes)
    g.create(*rels)
    return g

def test_walk(graph):

    just_name = lambda a: a.get('name', 'unknown')
    # first get the id of our mother
    n = graph.cypher.execute_one("MATCH (n:INDI {NAME: 'mother'}) return n")
    id = int(n.ref.split('/')[1])

    mother = fwalk(graph, {"i": id})
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


def test_walk_api(graph, client):
    r = client.get('/fwalk?i=4&t=1')
    mother = r.json
    assert len(mother.keys()) == 10


def test_bad_params(graph, client):
    r = client.get('/fwalk')
    assert r.status_code == 400
    r = client.get('/fwalk?t=aaa')
    assert r.status_code == 400