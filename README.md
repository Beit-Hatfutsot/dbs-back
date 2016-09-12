# Beit-Hatfusot Backend

Welcome to the API server of the museum of the jewish people.  The code is in
Python using Flask and MongoDB.  The API docs are at
http://api.dbs.bh.org.il/v1/docs

The server is built on top of 6 datasets the museum has collected in the last four
decades.  We have >72,000 Pictures and >1,100 movies. We have text articles
about >6,000 communities >8,000 luminaries and >17,000 family names.

The last dataset is of family trees.
People have contributed to the museum ~11,000 trees with ~5,000,000 individuals.

## Installation

This server uses MongoDB so you'll have to have one up and running.
Mongo installation is quite simple, just read the
[manual](https://docs.mongodb.com/manual/installation/).

While a search engine is not a must, it is recommended to install
[Elasticsearch](https://www.elastic.co/downloads/elasticsearch).
Once you have MongoDB installed you can go on to install the python code:

### Linux

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

To load the search engine with the dump you restores run:

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
will use your local server you just need to run, in separate window:

    $ API_SERVER=local gulp serve

(the API_SERVER part tells the frontend to use a server at localhost:5000)

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
