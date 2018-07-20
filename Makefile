.PHONY: publish pytest clean lint flake8 xmllint clear-objects build test

build:
	./setup.py sdist && ./setup.py bdist_wheel

test: pytest lint flake8 xmllint

publish:
	twine upload dist/* && git push && git push --tags

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
	python -c "from coralillo import Engine; eng=Engine(); eng.lua.drop(args=['*'])"
	mongo cacahuate --eval "db.pointer.drop()"
	mongo cacahuate --eval "db.execution.drop()"
	sudo rabbitmqctl purge_queue cacahuate_process
