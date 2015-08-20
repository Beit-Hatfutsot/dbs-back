# bhs API service

Installation
------------

On Debian/Ubuntu run::

    $ git clone git@bitbucket.org:bhonline/bhs_api.git
    $ cd bhs_api
    $ make external_dependencies
    $ virtualenv venev
    $ . venv/bin/activate
    $ pip install -r requirments.txt


Development
-----------

Don't forget to activate the virtual environment (and update if needed)

Deployment
----------

ssh into the server and run `make`
