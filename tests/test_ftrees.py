import pytest
from py2neo import Graph, Node, Relationship
from family_tree import fwalk
from pytest_flask.plugin import client

@pytest.fixture
def graph(request):
    g = Graph("http://neo4j:bhonline@localhost:7474/db/data")
    def fin():
        g.cypher.execute("MATCH (n { tree_id: '1' }) optional match (n)-[r]-() delete n,r")
    request.addfinalizer(fin)

    nodes = [
        Node("Person", tree_id='1', id='1', name="grandfather's father"),
        Node("Person", tree_id='1', id='2', name="grandfather"),
        Node("Person", tree_id='1', id='3', name="grandmother"),
        Node("Person", tree_id='1', id='4', name="mother"),
        Node("Person", tree_id='1', id='5', name="father"),
        Node("Person", tree_id='1', id='6', name="uncle"),
        Node("Person", tree_id='1', id='7', name="aunt"),
        Node("Person", tree_id='1', id='8', name="brother"),
        Node("Person", tree_id='1', id='9', name="brother"),
        Node("Person", tree_id='1', id='10', name="sister"),
    ]

    rels = [ Relationship(nodes[0], "FATHER_OF", nodes[1]),
             Relationship(nodes[1], "FATHER_OF", nodes[4]),
             Relationship(nodes[1], "FATHER_OF", nodes[5]),
             Relationship(nodes[2], "MOTHER_OF", nodes[4]),
             Relationship(nodes[4], "FATHER_OF", nodes[7]),
             Relationship(nodes[4], "FATHER_OF", nodes[8]),
             Relationship(nodes[4], "FATHER_OF", nodes[9]),
             Relationship(nodes[3], "MOTHER_OF", nodes[7]),
             Relationship(nodes[2], "MOTHER_OF", nodes[8]),
             Relationship(nodes[2], "MOTHER_OF", nodes[9]),
            ]
    g.create(*nodes)
    g.create(*rels)
    return g


def test_walk(graph):
    r = fwalk(str(graph.uri), individual_id="4", tree_id="1", radius=1)
    assert len(r) == 1
    r = fwalk(str(graph.uri), individual_id="4", tree_id="1", radius=2)
    assert len(r) == 2
    r = fwalk(str(graph.uri), individual_id="4", tree_id="1", radius=3)
    assert len(r) == 6


def test_walk_api(graph, client):
    r = client.get('/fwalk?p=4&t=1&r=1')
    assert len(r.json) == 1
    r = client.get('/fwalk?p=4&t=1&r=2')
    assert len(r.json) == 2
    r = client.get('/fwalk?p=4&t=1')
    assert len(r.json) == 6
