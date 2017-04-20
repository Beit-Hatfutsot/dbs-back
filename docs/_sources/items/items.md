# Group Item

## Get Item/s [GET /v1/item/{slugs}]
Get specific items according to their slugs

+ Parameters
    + slugs: `place_paris,person_1130;0.I3552` (string, required)
        Comma-separated list of slugs to fetch

+ Response 200 (application/json)

            [
                // list of item objects (see Item Models section for details)
                <!-- include(item_place.json) -->,
                <!-- include(item_person.json) -->
            ]


# Group Item Models
Every item represents an item in one of our collections.

Each item have some common properties and some unique properties depending on the collection.

## Item
The base item, includes attributes common to all collections.

+ Model (application/json)

            <!-- include(item_base.json) -->


## Place
Extends the base item with place specific attributes

+ Model (application/json)

            <!-- include(item_place.json) -->


## Person
Extends the base item with person specific attributes

+ Model (application/json)

            <!-- include(item_person.json) -->
