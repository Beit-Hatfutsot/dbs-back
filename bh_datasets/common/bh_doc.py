class BhDoc(object):

    def __init__(self, source, id, titles=None, link=None):
        self.source = source
        self.id = id
        self.titles = titles
        self.link = link


class BhDocImage(BhDoc):

    def __init__(self, source, id, image_link=None, **kwargs):
        super(BhDocImage, self).__init__(source, id, **kwargs)
