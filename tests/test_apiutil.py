import pytest
from werkzeug.exceptions import BadRequest


def test_int_arg_parses_clamps_and_rejects(app):
    from xissite.apiutil import int_arg
    with app.test_request_context('/?n=7&big=9999&bad=x'):
        assert int_arg('n', 1) == 7
        assert int_arg('missing', 3) == 3
        assert int_arg('big', 1, 1, 100) == 100
        assert int_arg('n', 1, 10) == 10
        with pytest.raises(BadRequest):
            int_arg('bad', 1)


def test_int_arg_reads_a_body_dict():
    from xissite.apiutil import int_arg
    assert int_arg('hours', 0, 1, 24, source={'hours': '12'}) == 12
    with pytest.raises(BadRequest):
        int_arg('hours', 0, source={'hours': 'soon'})


def test_json_errors_turns_400_and_404_into_json(app):
    from flask import Blueprint, Flask, abort
    from xissite.apiutil import json_errors
    bp = json_errors(Blueprint('t', __name__, url_prefix='/t'))

    @bp.route('/bad')
    def bad():
        raise BadRequest('nope')

    @bp.route('/missing')
    def missing():
        abort(404, description='no such thing')

    test_app = Flask('t')
    test_app.register_blueprint(bp)
    c = test_app.test_client()
    assert c.get('/t/bad').get_json() == {'error': 'nope'}
    assert c.get('/t/bad').status_code == 400
    assert c.get('/t/missing').get_json() == {'error': 'no such thing'}
    assert c.get('/t/missing').status_code == 404
