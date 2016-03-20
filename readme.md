# bhs API service

Installation
------------

On Debian/Ubuntu run::

    $ git clone git@bitbucket.org:bhonline/api.git
    $ cd api
    $ make external_dependencies
    $ virtualenv env
    $ . env/bin/activate
    $ pip install -r requirments.txt


Development
-----------

Don't forget to activate the virtual environment (and update if needed)

Deployment
----------

Deployment is done by::

    $ fab -H <host> deploy_server:<branch || 'dev' >

