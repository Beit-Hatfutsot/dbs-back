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
