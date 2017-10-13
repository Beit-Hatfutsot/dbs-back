from datapackage_pipelines.wrapper import ingest, spew
from datapackage_pipelines.utilities.resources import PROP_STREAMING
import elasticsearch.helpers
from elasticsearch import Elasticsearch
from temp_loglevel import temp_loglevel
import settings


parameters, datapackage, resource_iterator = ingest()
stats = {"total loaded rows": 0, "not allowed rows": 0}


def is_allowed_row(row):
    return row["StatusDesc"] == "Completed" and \
           row["RightsDesc"] == "Full" and \
           row["DisplayStatusDesc"] != "Internal Use" and \
           (row["UnitText1_En"] not in [None, ''] or row["UnitText1_He"] not in [None, ''])


def filter_row(row):
    global stats
    stats["total loaded rows"] += 1
    if is_allowed_row(row):
        yield {k: str(v) for k, v in row.items()}
    else:
        stats["not allowed rows"] += 1


def get_resources():
    yield get_resource()

def get_resource():
    global parameters
    es = Elasticsearch(settings.SITEMAP_ES_HOST)
    with temp_loglevel():
        for i, doc in enumerate(elasticsearch.helpers.scan(es, index=settings.SITEMAP_ES_INDEX, scroll=u"3h")):
            if not parameters.get("stop-after-rows") or i < int(parameters.get("stop-after-rows")):
                filtered_row = filter_row({"index": doc["_index"],
                                           "doc_type": doc["_type"],
                                           "doc_id": doc["_id"],
                                           "UnitId": doc["_source"].get("UnitId"),
                                           "RightsCode": doc["_source"].get("RightsCode"),
                                           "RightsDesc": doc["_source"].get("RightsDesc"),
                                           "StatusDesc": doc["_source"].get("StatusDesc"),
                                           "DisplayStatusDesc": doc["_source"].get("DisplayStatusDesc"),
                                           "UnitType": doc["_source"].get("UnitType"),
                                           "Slug_En": doc["_source"]["Slug"].get("En") if doc["_source"].get("Slug") else "",
                                           "Slug_He": doc["_source"]["Slug"].get("He") if doc["_source"].get("Slug") else "",
                                           "UnitText1_En": doc["_source"]["UnitText1"].get("En") if doc["_source"].get("UnitText1") else "",
                                           "UnitText1_He": doc["_source"]["UnitText1"].get("He") if doc["_source"].get("UnitText1") else "",
                                           "Header_En": doc["_source"]["Header"].get("En") if doc["_source"].get("Header") else "",
                                           "Header_He": doc["_source"]["Header"].get("He") if doc["_source"].get("Header") else "",
                                           })
                yield from filtered_row
            else:
                break


datapackage = {"name": "_",
               "resources": [{"name": "es_data", "path": "es_data.csv", PROP_STREAMING: True,
                              "schema": {"fields": [{"name": "index", "type": "string"},
                                                    {"name": "doc_type", "type": "string"},
                                                    {"name": "doc_id", "type": "string"},
                                                    {"name": "UnitId", "type": "string"},
                                                    {"name": "RightsCode", "type": "string"},
                                                    {"name": "RightsDesc", "type": "string"},
                                                    {"name": "StatusDesc", "type": "string"},
                                                    {"name": "DisplayStatusDesc", "type": "string"},
                                                    {"name": "UnitType", "type": "string"},
                                                    {"name": "Slug_En", "type": "string"},
                                                    {"name": "Slug_He", "type": "string"},
                                                    {"name": "UnitText1_En", "type": "string"},
                                                    {"name": "UnitText1_He", "type": "string"},
                                                    {"name": "Header_En", "type": "string"},
                                                    {"name": "Header_He", "type": "string"}]}}]}


spew(datapackage, get_resources(), stats)
