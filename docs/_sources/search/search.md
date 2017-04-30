# Group Database Search


## General search [GET /v1/search{?q,collection,from_,size,first,with_persons}]

This view initiates a full text search on all our collections.

+ Parameters
    + q: `netta` (string)
        The search string, using [elasticsearch query string syntax](https://www.elastic.co/guide/en/elasticsearch/reference/2.4/query-dsl-query-string-query.html#query-string-syntax)
    + collection (string, optional)
        A comma separated list of collections to search in.
        + Members
            + movies
            + places
            + personalities
            + photoUnits
            + familyNames
            + persons
    + from_ (number, optional)
        Which search result to start from.
    + size (number, optional)
        How many results to return.
    + with_persons (enum, optional)
        If to include persons results when searching over multiple collections
        + Members
            + 1

+ Response 200 (application/json)

            <!-- include(search_results.json) -->


## Persons advanced search [GET /v1/search<!-- include(persons_advanced_search_params.md) -->]

Advanced search on persons, must have at last one of either q param (as in general search) or the person specific search params

<!-- include(persons_advanced_search_params_description.md) -->

+ Response 200 (application/json)

            <!-- include(search_results.json) -->