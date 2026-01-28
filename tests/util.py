def create_json_schema():
    return {
        "$schema": "https://json-schema.org/draft-04/schema#",
        "title": "response"
    }


def name_and_description_combinations(at_least_one=False):
    combinations = [] if at_least_one else [({})]
    combinations += [
        ({'name': 'foo'}),
        ({'description': 'foo'}),
        ({'name': 'foo', 'description': ''}),
        ({'name': '', 'description': 'bar'}),
        ({'name': 'foo', 'description': 'bar'}),
        ({'name': '', 'description': ''}),
    ]
    return combinations


def metadata():
    return {'foo': 'bar'}


def assert_in_response(field, response):
    assert field in response, f'Missing {field} in response'
