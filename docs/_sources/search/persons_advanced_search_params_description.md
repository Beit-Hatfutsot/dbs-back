+ Parameters
    + collection: `persons` (enum, required) - The advanced persons search requires collection to be persons
        + Members
            + persons
    + q (string, optional) - same as in [general search](#database-search-general-search) except: 1. it's optional   2. it searches in the person places as well
    + from_ (number, optional) - see [general search](#database-search-general-search)
    + size (number, optional) - see [general search](#database-search-general-search)
    + first (string, optional) - first name
    + first_t: `like` (enum, optional) - first name <!-- include(text_search_type_members.md) -->
    + last (string, optional) - last name
    + last_t: `like` (enum, optional) - last name <!-- include(text_search_type_members.md) -->
    + pob (string, optional) - place of birth
    + pob_t: `like` (enum, optional) - place of birth <!-- include(text_search_type_members.md) -->
    + pom (string, optional) - place of marriage
    + pom_t: `like` (enum, optional) - place of marriage <!-- include(text_search_type_members.md) -->
    + pod (string, optional) - place of death
    + pod_t: `like` (enum, optional) - place of death <!-- include(text_search_type_members.md) -->
    + place (string, optional) - search over all place fields, if any matches it will return the result
    + place_t: `like` (enum, optional) - combined place field <!-- include(text_search_type_members.md) -->
    + yob (number, optional) - year of birth
    + yob_t: `pmyears` (enum, optional) - year of birth <!-- include(year_search_type_members.md) -->
    + yob_v: <!-- include(year_search_v_param.md) -->
    + yom (number, optional) - year of marriage
    + yom_t: `pmyears` (enum, optional) - year of marriage <!-- include(year_search_type_members.md) -->
    + yom_v: <!-- include(year_search_v_param.md) -->
    + yod (number, optional) - year of death
    + yod_t: `pmyears` (enum, optional) - year of death <!-- include(year_search_type_members.md) -->
    + yod_v: <!-- include(year_search_v_param.md) -->
    + sex (enum, optional) - **F**: Female, **M**: Male, **U**: Unkonwn / Unspecified
        + Members
            + F
            + M
            + U
    + treenum (number, optional) - Beit Hatfutsot tree number