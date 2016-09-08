# Beit-Hatfusot Backend

Welcome to the backend of the museum of the jewish people.  The code is in
Python using Flask licensed under AGPLv3.  Please feel free to
fork and send us pull requests.


## Installation

This server uses mongodb so you'll have to have one up and running.
Mongo installation is quite simple, just read the
[manual](https://docs.mongodb.com/manual/installation/).
Then run (for Debian/Ubuntu, if you're trying to install on other system, best
of luck and please send us some docs)::

	$ sudo apt-get install libffi-dev libjpeg62 libjpeg62-dev zlib1g-dev libssl-dev
    $ git clone git@bitbucket.org:bhonline/api.git
    $ cd api
    $ virtualenv env
    $ . env/bin/activate
    $ pip install -r requirments.txt

## Getting a DB

To play with the server you'll need some data in your db. Please download the
tar ball from [here]() and run

    $ tzr xf bhdata.tgz
    $ mongorestore -d bhdata dump/bhdata

## Installing a search engine

If you want to play around with search, you'll need to install
[Elasticsearch](https://www.elastic.co/downloads/elasticsearch). Once you have
Elasticsearch running you'll need to fill it with the data from Mongo:

    $ python scripts/dump_mongo_to_es.py --db bhdata

## Testing

    $ py.test tests

## Running a local server

A local server uses port 5000 and is activated by:

    $ python scripts/runserver.py

## Using the shell

If you want to play around with the flask shell you can start it using a special
script and gain access to the `app` object.

 $ python scripts/flask_shell.py

## Getting a the frontend

The frontend that uses this API server lives
[here](https://github.com/Beit-Hatfutsot/dbs-front). To run the fronend so it
will use your local server you just need to set `API_SERVER` to `local`.

## Contributing

Contributions from both Jews and Gentiles are welcomed! We even have a
`beginner` label to help you start with (hopefully) simple issues.
Once you have an issue, just follow these simple steps:

1. Fork it!
2. Create your feature branch: `git checkout -b my-new-feature`
3. Test your code
4. Commit your changes: `git commit -am 'Add some feature'`
5. Push to the branch: `git push origin my-new-feature`
6. Submit a pull request :D

### Updating the docs

If you've made any changes to the API please update the docs.
The documentation leaves in the `/docs` folder. We are using *API Blueprint*,
a markdown based format,  and [aglio](https://github.com/danielgtaylor/aglio)
to render it to HTML. Once you've updated the docs you'll have to regenerate
the html file::

    $ cd docs
    $ aglio -i index.apib -o index.html

and commit both files.
