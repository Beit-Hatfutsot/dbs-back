class MockRequests(object):

    def __init__(self):
        self.expected_gets = []

    def get(self, url, params):
        res = [tres for turl, tparams, tres in self.expected_gets if turl == url and sorted(tparams.items()) == sorted(params.items())]
        if len(res) == 1:
            return res[0]
        elif len(res) == 0:
            raise Exception("No response for MockRequests.get({url}, {params})".format(url=url, params=params))
        else:
            raise Exception("More then 1 expected response for MockRequests.get({url}, {params})".format(url=url, params=params))

    def expect_get(self, url, params, response):
        self.expected_gets.append((url, params, response))


class MockJsonResponse(object):

    def __init__(self, response_data):
        self.response_data = response_data

    def json(self):
        return self.response_data
