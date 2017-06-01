from calibre.ebooks.metadata.sources.base import Source

class KindleHighResCovers(Source):
    name                    = 'Amazon hi-res covers (Kindle)'
    description             = 'Downloads high resolution covers from Amazon (only Kindle books)'
    capabilities            = frozenset(['cover'])
    author                  = 'Leonardo Brondani Schenkel <leonardo@schenkel.net>'
    version                 = (0, 1, 0)
    can_get_multiple_covers = True
    sources = frozenset([
        'http://z2-ec2.images-amazon.com/images/P/{0}.01.MAIN._SCRM_.jpg',
        'https://s3.cn-north-1.amazonaws.com.cn/sitbweb-cn/content/{0}/images/cover.jpg',
    ])

    def download_cover(self, log, result_queue, abort,
                       title=None, authors=None, identifiers={},
                       timeout=60, get_best_cover=False):
        urls = set()
        for id, value in identifiers.iteritems():
            is_asin   = id == 'asin' or id == 'mobi-asin' or id.startswith('amazon')
            is_kindle = len(value) == 10 and value.startswith('B')
            if is_asin and is_kindle:
                for source in self.sources:
                    url = source.format(value)
                    urls.add(url)
        if urls:
            self.download_multiple_covers(title, authors, urls, False,
                                          timeout, result_queue, abort, log,
                                          None)
