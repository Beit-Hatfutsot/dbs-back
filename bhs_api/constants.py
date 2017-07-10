
# mojp_dbs_pipelines creates all docs under "common" doctype
PIPELINES_ES_DOC_TYPE = "common"

# suggest works only for these languages
# pipelines ensure it enters a value to the "title_{lang}_suggest" field
SUPPORTED_SUGGEST_LANGS = ["he", "en"]
