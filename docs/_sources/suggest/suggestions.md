# Group Suggest


## General suggestions [GET /v1/suggest/*/{input}]

Get suggestion of BH DBS titles in which the first characters match the user's search input. **The API returns only suggestions that "Start with" the typed input, though it also includes empty "phonetic" and "contains" fields, which are currently inactive**. In this View, the API suggests completion of a query from all databases (Places, Personalities, PhotoUnits, FamilyNames, Persons and Movies). 

+ Parameters
    + input: `li` (string)
        Must be more than one character.

+ Response 200 (application/json)

            <!-- include(general_suggest.json) -->


## Suggest by specific collection  [GET /v1/suggest/{collection}/{input}]

Get suggestion of any DB collection titles in which the first characters match the user's search input. **The API returns only suggestions that "Start with" the typed input, though it also includes empty "phonetic" and "contains" fields, which are currently inactive**.

+ Parameters
    + input: `pr` (string)
        Must be more than one character.
    + collection: `places` (string)
        + Members
            + places
            + photoUnits
            + familyNames
            + personalities
            + persons
            + movies


+ Response 200 (application/json)

            <!-- include(suggest_by_collection.json) -->