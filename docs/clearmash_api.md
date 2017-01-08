# ClearMash API

*WORK IN PROGRESS*

This document describes ClearMash API calls the API server is using.
We are using 
[python-zeep](http://docs.python-zeep.org/) to tame the SOAP/WSDL beast and
get the data we need. The zeep also has a nice way of parsing the WSDLs,
so to dump a WSDL use:

    python -m zeep https://bh.clearmash.com/API/V5/Services/WebContentManagement.svc?wsdl

## Auhorization

To allow access to the sytstem you need a sceret client token. That token is
sent as `ClientToken`'s string value in the headers of every soap call.

## Entities

Acces to ClearMash entities is through its `WebContentManagement.svc` wsdl.

### Get Entity By UnitId

This is the easiest way to access the db and is used for thesting and not 
by the API.

<dl>
    <dt>Method</dt>
    <dd>GetDocument</dd>
    <dt>Parameters<dt>
    <dd>id</dd>
</dl>

### Get Entity By Slug

This is the main way to get an item's page.

<dl>
    <dt>Method</dt>
    <dd>LookupDocument</dd>
    <dt>Parameters</dt>
    <dd><pre>
LookupDocumentByLocalizedField(
    FieldId='_c6_beit_hatfutsot_bh_base_template_url_slug',
    Value=slug)
    </pre></dd>
</dl>

*FAILS*: the language field (aka ISO6391) is probably missing 

### Update Document

<dl>
    <dt>Method</dt>
    <dd>EditDocument</dd>
    <dt>Parameters</dt>
    <dd><pre>
EditWebDocumentParameters(
    EntityId=id,
    ApproveCriteria="AllPendingData",
    DataBaseChangeset=changeset,
    Entity=EntitySaveData(document))
    </pre></dd>
</dl>

We use this when we get a call back from clearmash indicating an entity was
updated. Then, we get the entity and if it has no slug, we
copy its `Document` and make the following changes to get an updated document:

* add an element in the 'Fields_LocalizedText.LocalizedTextDocumentField' array:
<pre>
{
    'Id': '_c6_beit_hatfutsot_bh_base_template_url_slug',
    'Value': {
        'LocalizedString': [
            {'ISO6391': 'en', 'Value': slug['en']},
            {'ISO6391': 'he', 'Value': slug['he']},
        ]
    }
}
</pre>

* add `TemplateId` based on `TemplateReference.TemplateId`
* remove `TemplateReference`

## Search

### General Search

<dl>
    <dt>Method</dt>
    <dd>TBD</dd>
    <dt>Parameters</dt>
    <dd>
    TBD
    </dd>
</dl>

Get a simple query, an optional collection name, and return a list of entities.
Used to support [general search page](http://test.dbs.bh.org.il/search). 

### Person Search

<dl>
    <dt>Method</dt>
    <dd>TBD</dd>
    <dt>Parameters</dt>
    <dd>
    TBD
    </dd>
</dl>


Get a complex query and return a list of person entities, used to support
[Family Tree search page](http://test.dbs.bh.org.il/person). The complex query
should support the following fields:

* place (string, optional)
    A place that the person been born, married or died in
* first_name: `Albert` (string, optional)
    Supports two suffixes - `;prefix` to look for names
    begining with the given string and `;phonetic` to use phonetic matching.
* maiden_name (string, optional)
    Supports two suffixes - `;prefix` to look for names
    begining with the given string and `;phonetic` to use phonetic matching.
* last_name: `Einstein` (string, optional)
    Supports two suffixes - `;prefix` to look for names
    begining with the given string and `;phonetic` to use phonetic matching.
* birth_place (string, optional)
    Supports two suffixes - `;prefix` to look for names
    begining with the given string and `;phonetic` to use phonetic matching.
* marriage_place (string, optional)
    Supports two suffixes - `;prefix` to look for names
    begining with the given string and `;phonetic` to use phonetic matching.
* death_place (string, optional)
    Supports two suffixes - `;prefix` to look for names
    begining with the given string and `;phonetic` to use phonetic matching.
* birth_year (number, optional)
    Supports an optional fudge factor suffix, i.e. to search for a person
    born between 1905 to 1909 use "1907:2"
* marriage_year (number, optional)
    Supports an optional fudge factor suffix.
* death_year (number, optional)
    Supports an optional fudge factor suffix.
* tree_number (number, optional)
    A valid tree number, like 7806
* sex (enum[String], optional)

### Auto complete

<dl>
    <dt>Method</dt>
    <dd>TBD</dd>
    <dt>Parameters</dt>
    <dd>
    TBD
    </dd>
</dl>

Help the user find the place or the family name he's looking for. Should return
Soundex completion options as well as classic suggestions.
