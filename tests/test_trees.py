from datetime import datetime
import os
import pytest


def given_mock_migrate_config():
    return type('MockMigrateConfig', (object,), {
        "sql_server": "mock-sql-server",
        "sql_user": "user",
        "sql_password": "password",
        "sql_db": "db",
        "gentree_mount_point": os.path.join(os.path.dirname(__file__), "gentrees")
    })


def given_mock_migrate_environment(mocker):
    mocker.patch("bhs_api.utils.get_conf", return_value=given_mock_migrate_config())
    mocker.patch("pymssql.connect")


def given_mock_gedcom_tree_with_single_person(deceased=True, birth_year=1679, death_year=1755, gender="F"):
    gedcom = type('MockGedcom', (object,), {
        "as_list": [
            type('MockGedcomHead', (object,), {
                "children": [
                    type("MockGedcomChild", (object,), {"tag": "SOUR", "value": "FTW", "children": []}),
                    type("MockGedcomChild", (object,), {"tag": "DATE", "value": "21 AUG 2008", "children": []}),
                    type("MockGedcomChild", (object,), {"tag": "GEDC", "value": None, "children": [
                        type("MockGedcomChild", (object,), {"tag": "VERS", "value": "5.5", "children": []}),
                        type("MockGedcomChild", (object,), {"tag": "FORM", "value": "LINEAGE-LINKED", "children": []})
                    ]})
                ]
            })
        ],
        "as_dict": {
            "@I01@": type('MockGedcomPerson', (object,), {
                "pointer": "@I01@", "is_individual": True,
                "gender": gender,  # can be one of "F" / "M" / ""
                "deceased": deceased,  # based on the gedcom DEAT attribute
                "private": False,
                "name": "Shneor the milk man",
                "birth_year": birth_year,
                "death_year": death_year,
                "marriage_years": None,
                "children": [],
            }),
        },
        "families": lambda self, node, attr: [],
        "get_parents": lambda self, e: []
    })


def test_migrate_trees(mocker):
    given_mock_migrate_environment(mocker)
    from scripts.migrate import migrate_trees, parse_doc, get_collection_id_field
    cursor = [
        {"GenTreeNumber": 666, "UpdateDate": datetime(1970, 8, 17, 21, 10, 38), "GenTreePath": "T666.ged"}
    ]
    since_timestamp = 19764538  # datetime(1970, 8, 17, 20, 8, 58)
    until_timestamp = 19768538  # datetime(1970, 8, 17, 21, 15, 38)
    treenums = None
    saved_docs = []
    def on_save(row, collection_name):
        doc = parse_doc(row, collection_name)
        id_field = get_collection_id_field(collection_name)
        saved_docs.append((row, collection_name, id_field, doc))
        # update_row.delay(doc, collection_name)
        return doc
    assert migrate_trees(cursor, since_timestamp, until_timestamp, treenums, on_save=on_save) == 1
    assert saved_docs[0][0]["id"] == "I29"  # row
    assert saved_docs[0][1] == "persons"  # collection_name
    assert saved_docs[0][2] == "id"  # collection_id_field
    assert saved_docs[0][3]["id"] == "I29"  # doc
    assert saved_docs[0][3]["deceased"] == False
    assert saved_docs[3][3]["deceased"] == True


def test_gedcom_to_persons(mocker):
    from migration.family_trees import Gedcom2Persons

    tree_num = None
    file_id = None
    saved_data = []
    on_save = lambda data, collection: saved_data.append(data)
    Gedcom2Persons(gedcom(), tree_num, file_id, on_save)
    print(saved_data)
