import re
import urllib
from calibre import as_unicode
from calibre import browser
from calibre.utils.cleantext import clean_ascii_chars
from calibre.ebooks.metadata.sources.base import Source, Option
from contextlib import closing
from lxml.html import fromstring
from urlparse import urljoin

class KindleHighResCovers(Source):
    name                    = 'Kindle hi-res covers'
    description             = 'Downloads high resolution covers for Kindle editions from Amazon'
    capabilities            = frozenset(['cover'])
    author                  = 'Leonardo Brondani Schenkel <leonardo@schenkel.net>'
    version                 = (0, 4, 0)
    can_get_multiple_covers = True

    KEY_MAX_COVERS = 'max_covers'

    options = (Option(KEY_MAX_COVERS, 'number', 2, _('Maximum number of covers to get'),
                      _('The maximum number of covers to get from amazon.com (since we try to get the covers from 2 sources, you might end up with two versions of each retrieved cover).')),
    )

    def download_cover(self, log, result_queue, abort,
                       title=None, authors=None, identifiers={},
                       timeout=60, get_best_cover=False):
        urls = get_cover_urls(log, title, authors, identifiers, timeout)
        log.info('Cover URLs: ' + repr(urls))

        if urls:
            log.info('Create link to download cover')
            self.download_multiple_covers(title, authors, urls, False,
                                          timeout, result_queue, abort, log,
                                          None)

def get_cover_urls(log, title, authors, identifiers, timeout):
    sources = frozenset([
        'http://z2-ec2.images-amazon.com/images/P/{0}.01.MAIN._SCRM_.jpg',
        'https://s3.cn-north-1.amazonaws.com.cn/sitbweb-cn/content/{0}/images/cover.jpg',
    ])
    urls = set()
    asins = set()
    # check for ASINs identifiers first
    for id, value in identifiers.iteritems():
        is_asin   = id == 'asin' or id == 'mobi-asin' or id.startswith('amazon')
        is_kindle = is_kindle_asin(value)
        if is_asin and is_kindle:
            log.info('ASIN present in metadata: %s' % value)
            asins.add(value)
    # otherwise use Goodreads id to find Kindle editions
    if not asins:
        log.info('ASIN not present in metadata')
        goodreads = identifiers.get('goodreads')
        if goodreads:
            log.info('Goodreads id present in metadata: %s' % value)
            asins = search_asins_goodreads(log, goodreads)
        else:
            log.info('Goodreads id not present in metadata')
    # otherwise search Goodreads to find Kindle editions
    # use ISBN if available, otherwise use title+author
    if not asins:
        isbn = identifiers.get('isbn')
        if isbn:
            log.info('ISBN present in metadata: %s', isbn)
            query = isbn
        else:
            log.info('ISBN not present in metadata')
            query = ''
            if title:
                query = title
                if authors and authors[0]:
                    query = query + ' ' + authors[0]
        if query:
            edition = search_edition_goodreads(log, query)
            if edition:
                asins = search_asins_goodreads(log, edition)
    # now convert all ASINs into the download URLs
    if asins:
        for asin in asins:
            for source in sources:
                url = source.format(asin)
                urls.add(url)
    return list(urls)

def is_kindle_asin(value):
    return value and len(value) == 10 and value.startswith('B')

goodreads_url = 'https://www.goodreads.com'

def search_edition_goodreads(log, query):
    edition_url = None

    br = browser()
    search_url = urljoin(goodreads_url, '/search?q=' + urllib.quote_plus(query))
    log.info('Searching Goodreads for book: %s' % search_url)
    with closing(br.open(search_url)) as response:
        url = br.geturl()
        if url == search_url:
            # There was no perfect match, get the first result
            doc = fromstring(response.read())
            edition_url = None
            books = doc.xpath('//*[@itemtype="http://schema.org/Book"]')
            if books:
                book = books[0]
                url = book.xpath('.//*[@itemprop="url"]/@href')[0]
                if url:
                    edition_url = url
        else:
            # There was a perfect match and we were redirected to the edition
            edition_url = url

    if edition_url:
        edition_url = urljoin(goodreads_url, edition_url)
    return edition_url

def search_asins_goodreads(log, edition):
    try:
        number = int(edition)
        edition_url = '/book/show/' + str(number)
    except ValueError:
        edition_url = edition
    edition_url = urljoin(goodreads_url, edition_url)

    br = browser()
    # parse the details page and get the link to list all editions
    log.info('Fetching book details: %s' % edition_url)
    with closing(br.open(edition_url)) as response:
        doc = fromstring(response.read())
        editions_url = doc.xpath('//div[@class="otherEditionsLink"]/a/@href')
        if editions_url:
            editions_url = editions_url[0]
        else:
            return set()
        editions_url = urljoin(goodreads_url, editions_url)

    # list all Kindle editions of the book
    editions_url = urljoin(editions_url, '?expanded=true&filter_by_format=Kindle+Edition&per_page=100')
    log.info('Fetching Kindle editions: %s' % editions_url)
    with closing(br.open(editions_url)) as response:
        doc = fromstring(response.read())
        asins = set()
        for value in doc.xpath('//*[@class="dataValue"]//text()'):
            value = value.strip()
            if is_kindle_asin(value):
                asins.add(value)
        return asins

import getopt
import logging
import sys
if __name__ == "__main__":
    title = None
    author = None
    identifiers = {
        'asin': None,
        'goodreads': None,
        'isbn': None,
    }
    
    opts, args = getopt.gnu_getopt(sys.argv, '', ['title=', 'author=', 'isbn=', 'asin=', 'goodreads='])
    for o, a in opts:
        if o == '--asin':
            identifiers['asin'] = a
        elif o == '--author':
            author = a
        elif o == '--goodreads':
            identifiers['goodreads'] = a
        elif o == '--isbn':
            identifiers['isbn'] = a
        elif o == '--title':
            title = a
   
    logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)
    log = logging.getLogger()
    urls = get_cover_urls(log, title, [ author ], identifiers, 60)
    for url in urls:
        print(url)

