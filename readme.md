#  API server

# Beit-Hatfusot Back-End README

Welcome to the backend of the museum of the jewish people.  The code is in
Python using Flask licensed under AGPLv3.  Please feel free to
fork and send us pull requests.

## Installation

On Debian/Ubuntu run::

	$ sudo apt-get install libffi-dev libjpeg62 libjpeg62-dev zlib1g-dev libssl-dev
    $ git clone git@bitbucket.org:bhonline/api.git
    $ cd api
    $ virtualenv env
    $ . env/bin/activate
    $ pip install -r requirments.txt

## Testing

    $ py.test tests

## Using the shell

If you want to play around with the flask shell you can start it using a special
script and gain access to the `app` object.

 $ python scripts/flask_shell.py

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
The documentation leaves in the `/docs` folder. We are using API Blueprint,
a markdown based format,  and [aglio](https://github.com/danielgtaylor/aglio)
to render it to HTML. Once you've updated the docs you'll have to regenerate
the html file::

    $ cd docs
    $ aglio -i index.apib -o index.html

and commit the two files.
