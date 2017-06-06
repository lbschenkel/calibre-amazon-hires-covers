import urllib
from lxml.html import fromstring
from calibre import as_unicode
from calibre import browser
from calibre.utils.cleantext import clean_ascii_chars
from calibre.ebooks.metadata.sources.base import Source, Option

class KindleHighResCovers(Source):
    name                    = 'Amazon hi-res covers'
    description             = 'Downloads high resolution covers from Amazon'
    capabilities            = frozenset(['cover'])
    author                  = 'Leonardo Brondani Schenkel <leonardo@schenkel.net>'
    version                 = (0, 1, 0)
    can_get_multiple_covers = True
    sources = frozenset([
        'http://z2-ec2.images-amazon.com/images/P/{0}.01.MAIN._SCRM_.jpg',
        'https://s3.cn-north-1.amazonaws.com.cn/sitbweb-cn/content/{0}/images/cover.jpg',
    ])
    
    KEY_MAX_COVERS = 'max_covers'

    options = (Option(KEY_MAX_COVERS, 'number', 2, _('Maximum number of covers to get'),
                      _('The maximum number of covers to get from amazon.com (since we try to get the covers from 2 sources, you might end up with two versions of each retrieved cover).')),
    )
    
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

        if not urls:
            log.info('No Kindle ASIN available for identification')
            found_id = self.get_asin_from_title_author(log, abort, title, authors, timeout)
            if found_id:
                log.info('ASIN found: %r'%found_id)
                for id_to_use in found_id:
                    for source in self.sources:
                        url = source.format(id_to_use)
                        urls.add(url)
            else:
                log.info('No ASIN found')

        if urls:
            log.info('Create link to download cover')
            self.download_multiple_covers(title, authors, urls, False,
                                          timeout, result_queue, abort, log,
                                          None)

    def create_query(self, log, title=None, authors=None):
        if title is not None:
            search_title = urllib.quote(title.encode('utf-8'))
        else:
            search_title = ''

        if authors is not None:
            search_author = urllib.quote(authors[0].encode('utf-8'))
        else:
            search_author = ''

        search_page = 'https://www.amazon.com/s/url=search-alias%3Ddigital-text&field-keywords=' + '%s%%20%s'%(search_author, search_title)

        return search_page

    def get_asin_from_title_author(self, log, abort, title, authors, timeout=30):
        log.info(u'\nStart search by author and title\nTitle:%s\nAuthors:%s\n'%(title, authors))
        br = browser()
        counter = self.prefs[KindleHighResCovers.KEY_MAX_COVERS]

        query = self.create_query(log, title=title, authors=authors)
        if query is None:
            log.error('Insufficient metadata to construct query')
            return
        try:
            log.info('Querying: %s'%query)
            response = br.open(query)
        except Exception as e:
            if callable(getattr(e, 'getcode', None)) and e.getcode() == 404:
                log.info('Failed to find match for ISBN: %s'%isbn)
            else:
                err = 'Failed to make identify query: %r'%query
                log.exception(err)
                return as_unicode(e)

        try:
            raw = response.read().strip()
            raw = raw.decode('utf-8', errors='replace')
            if not raw:
                log.error('Failed to get raw result for query: %r'%query)
                return
            root = fromstring(clean_ascii_chars(raw))

            try:
                results = root.xpath('//div[@id="atfResults" and @class]')[0]
            except IndexError:
                return

            if 's-result-list-parent-container' in results.get('class', ''):
                data_xpath = "descendant-or-self::li[@class and contains(concat(' ', normalize-space(@class), ' '), ' s-result-item ')]"
                format_xpath = './/a[contains(text(), "Kindle Edition") or contains(text(), "Kindle eBook")]//text()'
                asin_xpath = '@data-asin'
                author_xpath = './/span[starts-with(text(), "by ")]/following-sibling::span//text()'
                title_xpath = "descendant-or-self::h2[@class and contains(concat(' ', normalize-space(@class), ' '), ' s-access-title ')]//text()"
            elif 'grid' in results.get('class', ''):
                data_xpath = '//div[contains(@class, "prod")]'
                format_xpath = (
                    './/ul[contains(@class, "rsltGridList")]'
                    '//span[contains(@class, "lrg") and not(contains(@class, "bld"))]/text()')
                asin_xpath = '@name'
                author_xpath = './/h3[@class="newaps"]//span[contains(@class, "reg")]//text()'
                title_xpath = './/h3[@class="newaps"]/a//text()'
            elif 'ilresults' in results.get('class', ''):
                data_xpath = '//li[(@class="ilo")]'
                format_xpath = (
                    './/ul[contains(@class, "rsltGridList")]'
                    '//span[contains(@class, "lrg") and not(contains(@class, "bld"))]/text()')
                asin_xpath = '@name'
                author_xpath = './/h3[@class="newaps"]//span[contains(@class, "reg")]//text()'
                title_xpath = './/h3[@class="newaps"]/a//text()'
            elif 'list' in results.get('class', ''):
                data_xpath = '//div[contains(@class, "prod")]'
                format_xpath = (
                    './/ul[contains(@class, "rsltL")]'
                    '//span[contains(@class, "lrg") and not(contains(@class, "bld"))]/text()')
                asin_xpath = '@name'
                author_xpath = './/h3[@class="newaps"]//span[contains(@class, "reg")]//text()'
                title_xpath = './/h3[@class="newaps"]/a//text()'
            else:
                return

            asin_list = []
            for data in root.xpath(data_xpath):
                if counter <= 0:
                    break

                # Even though we are searching digital-text only Amazon will still
                # put in results for non Kindle books (author pages). Se we need
                # to explicitly check if the item is a Kindle book and ignore it
                # if it isn't.
                format = ''.join(data.xpath(format_xpath))
                if 'kindle' not in format.lower():
                    continue

                #Compare author last name with the author name for the book we found
                #to eliminate some false positive. We check only last name to match
                #abbreviated first name.
                found_author = ''.join(data.xpath(author_xpath))
                first_author = authors[0]
                last_name = first_author.rsplit(' ', 1)[-1]
                if last_name.lower() not in found_author.lower():
                    log.info('Found a book with the wrong author: %s'%found_author)
                    continue

                #Compare the searched title with the title of the book we found
                #to eliminate some false positive.
                found_title = ''.join(data.xpath(title_xpath))
                wrong_title = False
                for title_tokens in Source.get_title_tokens(self, title, strip_joiners=True, strip_subtitle=False):
                    if title_tokens.lower() not in found_title.lower():
                        wrong_title = True
                        log.info('Found a book with the wrong title: %s'%found_title)
                        break
                    else:
                        continue
                if wrong_title:
                    continue

                asin = data.xpath(asin_xpath)
                asin = asin[0]
                is_kindle = len(asin) == 10 and asin.startswith('B')
                if is_kindle:
                    asin_list.append(asin)
                    counter -= 1
                else:
                    continue
            return asin_list

        except:
            msg = 'Failed to parse amazon.com page for query: %r'%query
            log.exception(msg)
            return msg
