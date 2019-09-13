from cacahuate.http.wsgi import app


@app.route('/v1/execution/<id>/summary', methods=['GET'])
def execution_template(id):
    return {
        'hello': 'template',
    }
