from datetime import datetime
import os
from migration.family_trees import Gedcom2Persons, THIS_YEAR


def given_mock_migrate_config():
    return type('MockMigrateConfig', (object,), {
        "sql_server": "mock-sql-server",
        "sql_user": "user",
        "sql_password": "password",
        "sql_db": "db",
        "gentree_mount_point": os.path.join(os.path.dirname(__file__), "gentrees"),
        "queries_repo_path": None
    })


def given_mock_migrate_environment(mocker):
    mocker.patch("bhs_api.utils.get_conf", return_value=given_mock_migrate_config())
    mocker.patch("pymssql.connect")


def given_mock_gedcom_tree_with_single_person(deceased=True, birth_year=1679, death_year=1755, gender="F"):
    return type('MockGedcom', (object,), {
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
        "get_parents": lambda self, e: [],
        "marriage_years": lambda self, e: [1345, 1355, 1377]
    })()


def gedcom_2_persons(gedcom):
    tree_num = None
    file_id = None
    saved_data = []
    on_save = lambda data: saved_data.append(data)
    Gedcom2Persons(gedcom, tree_num, file_id, on_save)
    return saved_data


def test_migrate_trees(mocker):
    given_mock_migrate_environment(mocker)
    from scripts.migrate import migrate_trees, parse_doc, get_collection_id_field
    cursor = [
        {"GenTreeNumber": 666, "UpdateDate": datetime(1970, 8, 17, 21, 10, 38), "GenTreePath": "T666.ged"}
    ]
    saved_docs = []
    def on_save(row):
        collection_name = "persons"
        doc = parse_doc(row, collection_name)
        id_field = get_collection_id_field(collection_name)
        saved_docs.append((row, collection_name, id_field, doc))
        # update_row.delay(doc, collection_name)
        return doc
    assert migrate_trees(cursor, on_save=on_save) == 1

    i29 = [doc for doc in saved_docs if doc[0]["id"] == "I29"][0]
    assert i29[0]["id"] == "I29"  # row
    assert i29[1] == "persons"  # collection_name
    assert i29[2] == "id"  # collection_id_field
    assert i29[3]["id"] == "I29"  # doc
    assert i29[3]["deceased"] == False

    i19 = [doc for doc in saved_docs if doc[0]["id"] == "I19"][0][3]
    assert i19["id"] == "I19"
    assert i19["deceased"] == True

    i9 = [doc for doc in saved_docs if doc[0]["id"] == "I09"][0][3]
    assert i9["marriage_years"] == [1933]
    assert i9["birth_year"] == 1911
    assert i9["death_year"] == 1965


def test_gedcom_to_persons():
    # person marked as deceased in gedcom - is deceased, regardless of other attributes
    gedcom = given_mock_gedcom_tree_with_single_person(deceased=True)
    persons_data = gedcom_2_persons(gedcom)
    assert persons_data[0]["deceased"] == True
    assert persons_data[0]["marriage_years"] == [1345, 1355, 1377]
    # person not marked as deceased - need to guess if he is deceased based on birth year
    # if born more then 100 years ago - he is considered deceased
    gedcom = given_mock_gedcom_tree_with_single_person(deceased=False, birth_year=1789)
    persons_data = gedcom_2_persons(gedcom)
    assert persons_data[0]["deceased"] == True
    # if born less then 100 years ago - he is considered alive
    gedcom = given_mock_gedcom_tree_with_single_person(deceased=False, birth_year=THIS_YEAR-60)
    persons_data = gedcom_2_persons(gedcom)
    assert persons_data[0]["deceased"] == False
