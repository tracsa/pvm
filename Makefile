.PHONY: release pytest clean lint flake8 xmllint clear-objects

release:
	./setup.py test && ./setup.py sdist && ./setup.py bdist_wheel && twine upload dist/* && git push && git push --tags

test: pytest lint flake8 xmllint

clean:
	rm -rf dist/

pytest:
	pytest -xvv

lint:
	pycodestyle --statistics --show-source --exclude=.env,.tox,dist,docs,build,*.egg .

flake8:
	flake8 --exclude=.env,.tox,dist,docs,build,*.egg .

xmllint:
	xml/validate.sh

clear-objects:
	.env/bin/python -c "from coralillo import Engine; eng=Engine(); eng.lua.drop(args=['*'])"
	mongo cacahuate --eval "db.pointer.drop()"
	mongo cacahuate --eval "db.execution.drop()"
	sudo rabbitmqctl purge_queue cacahuate_process
