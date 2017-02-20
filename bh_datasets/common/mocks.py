class MockRequests(object):

    def __init__(self):
        self.gets = []

    def get(self, url, params):
        self.gets.append((url, params))
