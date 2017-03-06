from datetime import datetime


class BhDoc(object):

    def __init__(self, source, id, titles=None, image_links=None, tags=None, descriptions=None):
        # (required) unique name of the source
        self.source = source
        # (required) unique id of the item for this source
        self.id = id
        # (optional) list of titles for this item
        # first title should be the primary title
        # other titles can be alternative titles or titles in other languages
        self.titles = titles
        # (optional) list of urls to download an image file
        # first image link should be the primary, followed by optional alternative images
        self.image_links = image_links
        # (optional) list of tags for this item
        self.tags = tags
        # (optional) list of descriptions for this item
        self.descriptions = descriptions

    def get_es_doc(self, with_current_time=False):
        """
        gets the elasticsearch representation of this item
        :return: a json serializable dict compatible with BH elasticsearch index
        """
        # YYYY-MM-ddTHH
        es_doc = {
            "id": self.id,
            "titles": self.titles,
            "image_links": self.image_links,
            "tags": self.tags
        }
        if with_current_time:
            es_doc["BH_SCRAPE_TIME"] = datetime.now().isoformat()
        return es_doc
