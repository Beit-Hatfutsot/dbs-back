# Group Suggest


## General suggestions [GET /v1/suggest/*/{input}]

Get suggestion of BH DBS titles in which the first characters match the user's input to search box. In this View, the API suggests completion of a query from all databases (Places, Personalities, PhotoUnits, FamilyNames, Persons and Movies). 

+ Parameters
    + input: `li` (string)
        Must be more than one character.

+ Response 200 (application/json)

            <!-- include(general_suggest.json) -->


## Suggest Family Name  [GET /v1/suggest/familyNames/{input}]

Get suggestion of familyNames DB titles in which the first characters match the user's input to the "Family Name" search box.

+ Parameters
    + input: `go` (string)
        Must be more than one character.

+ Response 200 (application/json)

            <!-- include(suggest_familyname.json) -->

## Suggest Place  [GET /v1/suggest/places/{input}]

Get suggestion of familyNames DB titles in which the first characters match the user's input to the "Family Name" search box.

+ Parameters
    + input: `be` (string)
        Must be more than one character.

+ Response 200 (application/json)

            <!-- include(suggest_places.json) -->