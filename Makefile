.PHONY: publish pytest clean lint xmllint clear-objects build test

build:
	./setup.py sdist && ./setup.py bdist_wheel

test: pytest lint xmllint xml_validate

publish:
	twine upload dist/* && git push && git push --tags

clean:
	rm -rf dist/

pytest:
	pytest -xvv

lint:
	flake8 --exclude=.env,.tox,dist,docs,build,*.egg .

xmllint:
	xmllint --noout --relaxng cacahuate/xml/process-spec.rng xml/*.xml

xml_validate:
	xml_validate xml/*.xml

clear-objects:
	python -c "from coralillo import Engine; eng=Engine(); eng.lua.drop(args=['*'])"
	mongo cacahuate --eval "db.pointer.drop()"
	mongo cacahuate --eval "db.execution.drop()"
	sudo rabbitmqctl purge_queue cacahuate_process
