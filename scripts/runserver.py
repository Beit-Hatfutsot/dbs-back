#!/usr/bin/env python
import argparse

from bhs_api import create_app


def flaskrun(db=None):
    ''' run's flask or does flask run?
        based on http://flask.pocoo.org/snippets/133/
    '''
    parser = argparse.ArgumentParser(description='Process some integers.')
    parser.add_argument('db', nargs='?',
                        help='db name to use - FAIL edit /etc/bhs/config.yml for now')
    parser.add_argument('-d', '--debug', help='turn debug on', default=False)
    args = parser.parse_args()
    if (args.db):
        #TODO: change the db
        pass
    app, conf = create_app()
    app.run(debug=args.debug)


if __name__ == "__main__":
    flaskrun()

