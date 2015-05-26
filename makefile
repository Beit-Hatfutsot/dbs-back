virtual_env = /home/bhs/venv
api = /home/bhs/api


all: reload venv external_dependencies bhs_common

pull:
	cd $(api) && git pull origin master

venv: $(virtual_env)/bin/activate

$(virtual_env)/bin/activate: requirements.txt
	test -d $(virtual_env) || virtualenv $(virtual_env)
	. $(virtual_env)/bin/activate; pip install --upgrade -r requirements.txt
	touch $(virtual_env)/bin/activate

external_dependencies:
	sudo apt-get install -y libffi-dev libjpeg62 libjpeg62-dev zlib1g-dev libssl-dev > /dev/null

bhs_common: venv
	pip install -e git+ssh://git@bitbucket.org/bhonline/bhs-common.git#egg=bhs_common

reload: pull
	sudo service uwsgi reload

reload_nginx:
	sudo service nginx reload

test:
	(cd tests; py.test)

#love:
#	$(info "Not with a computer, stupid!")
