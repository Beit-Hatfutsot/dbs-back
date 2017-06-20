# Group Linkify

## Linkify [POST /v1/linkify{?html}]

Given a block of html (or any unicode text) - returns a list of item titles and urls which appear in the text.

should send a standard form-urlencoded POST request containing parameter of html with value of the block of text to linkify

+ Request (application/x-www-form-urlencoded)

            html=the_html_to_linkify


+ Response 200 (application/json)

            {
                "familyNames": [
                    {"url": "http://dbs.bh.org.il/familyname/deri", "title": "DER'I"}
                ],
                "personalities": [
                    {"url": "http://dbs.bh.org.il/luminary/davydov-karl-yulyevich", "title": "Davydov, Karl Yulyevich"}
                ],
                "places": [
                    {"url": "http://dbs.bh.org.il/place/bourges", "title": "BOURGES"},
                    {"url": "http://dbs.bh.org.il/place/bozzolo", "title": "BOZZOLO"}
                ]
            }
