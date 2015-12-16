virtual_env = ~/venv

branch ?= master

all: test pull venv reload

pull:
	git checkout $(branch) && git pull origin $(branch)

venv: $(virtual_env)/bin/activate

$(virtual_env)/bin/activate: requirements.txt external_dependencies
	test -d $(virtual_env) || virtualenv $(virtual_env)
	. $(virtual_env)/bin/activate; pip install --upgrade -r requirements.txt
	touch $(virtual_env)/bin/activate

external_dependencies:
	sudo apt-get install -y libffi-dev libjpeg62 libjpeg62-dev zlib1g-dev libssl-dev > /dev/null

reload: pull
	sudo service uwsgi reload

reload_nginx:
	sudo service nginx reload

test: pull
	. $(virtual_env)/bin/activate && \
	py.test tests api.py

