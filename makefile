virtual_env = env

branch ?= master

all: pull venv test reload

pull:
	git checkout $(branch) && git pull origin $(branch)

venv: requirements.txt external_dependencies
	test -d $(virtual_env) || virtualenv $(virtual_env)
	. $(virtual_env)/bin/activate; pip install --upgrade -r requirements.txt
	touch $(virtual_env)/bin/activate

external_dependencies:
	sudo apt-get install -y libffi-dev libjpeg62 libjpeg62-dev zlib1g-dev libssl-dev > /dev/null

reload:
	sudo cp conf/api_uwsgi.ini /etc/uwsgi/vassals
	sudo service uwsgi reload

test:
	. $(virtual_env)/bin/activate; py.test tests bhs_api/views.py

