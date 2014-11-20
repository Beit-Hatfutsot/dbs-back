virtual_env = /home/bhs/venv
api = /home/bhs/api


all: reload venv

pull:
	cd $(api) && git pull origin master

venv: $(virtual_env)/bin/activate

$(virtual_env)/bin/activate: requirements.txt
	test -d $(virtual_env) || virtualenv $(virtual_env)
	. $(virtual_env)/bin/activate; pip install --upgrade -r requirements.txt
	touch $(virtual_env)/bin/activate

reload: pull
	sudo service uwsgi reload

reload_nginx:
	sudo service nginx reload

test:
	(cd tests; py.test)
