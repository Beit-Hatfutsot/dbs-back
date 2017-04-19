"""
logic and constants relating to persons
"""
import datetime


LIVING_PERSON_WHITELISTED_KEYS = ["partners",
                                  "name",
                                  "name_S",
                                  "tree_num",
                                  "name_lc",
                                  "tree_size",
                                  "sex",
                                  "parents",
                                  "siblings",
                                  "Slug",
                                  "tree_file_id",
                                  "id",
                                  "deceased",
                                  "tree_version"]

PERSONS_SEARCH_REQUIRES_ONE_OF = ["first", "last", "sex", "pob", "pom", "pod", "yob", "yom", "yod", "treenum"]
PERSONS_SEARCH_DEFAULT_PARAMETERS = {"first": None, "first_t": "exact",
                                     "last": None, "last_t": "exact",
                                     "sex": None,
                                     "pob": None, "pob_t": "exact",
                                     "pom": None, "pom_t": "exact",
                                     "pod": None, "pod_t": "exact",
                                     "yob": None, "yob_t": "exact", "yob_v": None,
                                     "yom": None, "yom_t": "exact", "yom_v": None,
                                     "yod": None, "yod_t": "exact", "yod_v": None,
                                     "treenum": None,}


def is_living_person(is_deceased, birth_year):
    if is_deceased:
        # deceased == not living!
        return False
    elif not isinstance(birth_year, (int, float)):
        # doesn't have a valid birth year
        # consider him as living (to be on the safe-side)
        return True
    elif datetime.datetime.now().year - int(birth_year) < 100:
        # born less then 100 years ago
        # consider him as living
        return True
    else:
        # consider him as dead
        return False
