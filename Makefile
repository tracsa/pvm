release:
	./setup.py test && ./setup.py sdist && ./setup.py bdist_wheel && twine upload dist/* && git push && git push --tags

clean:
	rm -rf dist/
