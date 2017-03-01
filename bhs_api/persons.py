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
