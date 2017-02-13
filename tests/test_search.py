from elasticsearch import Elasticsearch


def assert_error_response(res, expected_status_code, expected_error):
    assert res.status_code == expected_status_code
    assert res.data == """<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 3.2 Final//EN">
<title>{status_code} {status_msg}</title>
<h1>{status_msg}</h1>
<p>{error}</p>
""".format(error=expected_error, status_code=expected_status_code, status_msg="Bad Request" if expected_status_code == 400 else "Internal Server Error")


def dump_res(res):
    print(res.status_code, res.data)


def test_search_without_parameters_should_return_error(client):
    assert_error_response(client.get('/v1/search'), 400, "You must specify a search query")


def given_invalid_elasticsearch_client(app):
    app.es = Elasticsearch("192.0.2.0", timeout=0.000000001)


def test_search_without_elasticsearch_should_return_error(client, app):
    given_invalid_elasticsearch_client(app)
    assert_error_response(client.get('/v1/search?q=test'), 500, "Sorry, the search cluster appears to be down")
