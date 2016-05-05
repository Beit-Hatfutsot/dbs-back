from __future__ import with_statement
import os
from datetime import datetime
import logging

from fabric.api import *

API_SERVERS = {'bhs-dev': 'test-api.myjewishidentity.org',
               'bhs-prod': 'api.dbs.bh.org.il'}
LAST_UPDATE_FILE = '/var/run/bhs/last_update'
env.user = 'bhs'

env.now = datetime.now().strftime('%Y%m%d-%H%M')


def dev():
    env.hosts = ['bhs-dev']

def deploy(branch='dev'):
    push_code(branch)
    restart_api()

def restart_api():
    with cd("api"):
        with prefix('. env/bin/activate'):
            run('py.test tests bhs_api/*.py')
        '''
        run("cp conf/supervisord.conf ~")
        run("kill -HUP `cat /run/bhs/supervisord.pid`")
        run("supervisorctl restart all")
        '''
        sudo("cp conf/api-uwsgi.ini /etc/bhs/")
        # change the ini file to use the corrent uid for bhs
        sudo('sed -i "s/1000/`id -u bhs`/" /etc/bhs/api-uwsgi.ini')
        sudo("service uwsgi stop")
        # TODO bring uwsgi under supervisord
        sudo("cp conf/uwsgi /etc/init.d/")
        sudo("service uwsgi start")
        sudo("service uwsgi status")


def push_code(branch='dev'):
    local('find . -name "*.pyc" -exec rm -rf {} \;')
    with lcd(".."):
        local('tar czf api.tgz --exclude=env --exclude-vcs api')
        put('api.tgz', '~')
    run('tar xzf api.tgz')
    with cd("api"):
        run('virtualenv env')
        with prefix('. env/bin/activate'):
            run('pip install -r requirements.txt')


@hosts('bhs-infra')
def pull_mongo(dbname):
    if not os.path.isdir('snapshots/latest'):
        local('mkdir -p snapshots/latest')
    run('mongodump -d {}'.format(dbname))
    with cd('dump'):
        run('tar czf {0}.tgz {0}'.format(dbname))
        get('{}.tgz'.format(dbname),
            'snapshots/')
        run('rm {}.tgz'.format(dbname))
    with lcd('snapshots/latest'):
        local('tar xzvf ../{}.tgz'.format(dbname)
            )
        # delete the old db
        local('mongorestore --drop -d {0} {0}'.format(dbname))

@hosts('bhs-infra')
def update_related(db):
    with cd('api'), prefix('. env/bin/activate'):
        run('python batch_related.py --db {}'.format(db))

