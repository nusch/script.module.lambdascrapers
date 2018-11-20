# -*- coding: UTF-8 -*-
'''
    rlsbb scraper for Exodus forks.
    Sep 5 2018 - Cleaned and Checked

    Updated and refactored by someone.
    Originally created by others.
'''
import re,traceback,urllib,urlparse,json

from resources.lib.modules import cleantitle
from resources.lib.modules import client
from resources.lib.modules import control
from resources.lib.modules import debrid
from resources.lib.modules import log_utils
from resources.lib.modules import source_utils

class source:
    def __init__(self):
        self.priority = 1
        self.language = ['en']
        self.domains = ['rlsbb.to']             
        self.base_link = 'http://rlsbb.to/'     # http//search.rlsbb.to doesn't exist and .ru is too long

    # tried with cfscrape on rlsbb.ru to get cf cookies, but toooooo long (mini 15 sec to get them).
    # lucky we have choice here.

    def movie(self, imdb, title, localtitle, aliases, year):
        try:
            url = {'imdb': imdb, 'title': title, 'year': year}
            url = urllib.urlencode(url)
            return url
        except:
            failure = traceback.format_exc()
            log_utils.log('RLSBB - Exception: \n' + str(failure))
            return

    def tvshow(self, imdb, tvdb, tvshowtitle, localtvshowtitle, aliases, year):
        try:
            url = {'imdb': imdb, 'tvdb': tvdb, 'tvshowtitle': tvshowtitle, 'year': year}
            url = urllib.urlencode(url)
            return url
        except:
            failure = traceback.format_exc()
            log_utils.log('RLSBB - Exception: \n' + str(failure))
            return

    def episode(self, url, imdb, tvdb, title, premiered, season, episode):
        try:
            if url == None: return

            url = urlparse.parse_qs(url)
            url = dict([(i, url[i][0]) if url[i] else (i, '') for i in url])
            url['title'], url['premiered'], url['season'], url['episode'] = title, premiered, season, episode
            url = urllib.urlencode(url)
            return url
        except:
            failure = traceback.format_exc()
            log_utils.log('RLSBB - Exception: \n' + str(failure))
            return

    def sources(self, url, hostDict, hostprDict):
        try:
            log_utils.log("rlsbb debug")
            
            #base = self.base_link + "/"
            sources = []

            if url == None: return sources

            if debrid.status() == False: raise Exception()

            data = urlparse.parse_qs(url)   
            log_utils.log("data : " + str(data))      
            data = dict([(i, data[i][0]) if data[i] else (i, '') for i in data])        
            title = data['tvshowtitle'] if 'tvshowtitle' in data else data['title']
            hdlr = 'S%02dE%02d' % (int(data['season']), int(data['episode'])) if 'tvshowtitle' in data else data['year']
            premDate = ''
            
            querys = []
            r      = None

            # TVshows
            if 'tvshowtitle' in data:   

                log_utils.log("TV show")
                
                # test 1 - tvshowtitle + season and episode
                querys.append('%s-S%02dE%02d' % (data['tvshowtitle'], int(data['season']), int(data['episode'])))
                # test 2 - tvshowtitle + year (ex : titans-2018 , more and more got this format)
                querys.append('%s-%s-S%02dE%02d' % (data['tvshowtitle'], data['year'], int(data['season']), int(data['episode'])))
                # test 3 - tvshowtatle + season only (ex ozark-S02, group of episodes)
                querys.append('%s-S%02d' % (data['tvshowtitle'], int(data['season'])))
                # test 4 - try with tvshowtitle + year and season (ex Insomnia-2018-S01)
                querys.append('%s-%s-S%02d' % (data['tvshowtitle'], data['year'], int(data['season'])))

                log_utils.log("querys : " + str(querys))
                
                r = self.search(querys)

            else:
                log_utils.log("Movie")
                #  Movie
                querys.append('%s %s' % (data['title'], data['year']))
                r = self.search(querys)

            # looks like some shows have had episodes from the current season released in s00e00 format before switching to YYYY-MM-DD
            # this causes the second fallback search above for just s00 to return results and stops it from searching by date (ex. http://rlsbb.to/vice-news-tonight-s02)
            # so loop here if no items found on first pass and force date search second time around
            # This works till now, so only minor changes 
            for loopCount in range(0,2):
                #querys.clear()     # pyhton 3
                querys = []

                if loopCount == 1 or (r == None and 'tvshowtitle' in data) :                     # s00e00 serial failed: try again with YYYY-MM-DD
                    # http://rlsbb.to/the-daily-show-2018-07-24                                 ... example landing urls
                    # http://rlsbb.to/stephen-colbert-2018-07-24                                ... case and "date dots" get fixed by rlsbb
                    
                    premDate = re.sub('[ \.]','-',data['premiered'])
                    query = re.sub('[\\\\:;*?"<>|/\-\']', '', data['tvshowtitle'])              
                    
                    querys.append(query + "-" + premDate)

                    r = self.search(querys)

                posts = client.parseDOM(r, "div", attrs={"class": "content"})   # get all <div class=content>...</div>
                hostDict = hostprDict + hostDict                                # ?
                items = []
                
                for post in posts:
                    try:
                        u = client.parseDOM(post, 'a', ret='href')              # get all <a href=..... </a>
                        for i in u:                                             # foreach href url
                            try:
                                name = str(i)
                                if hdlr in name.upper(): items.append(name)
                                elif len(premDate) > 0 and premDate in name.replace(".","-"): items.append(name)      # s00e00 serial failed: try again with YYYY-MM-DD
                                # NOTE: the vast majority of rlsbb urls are just hashes! Future careful link grabbing would yield 2x or 3x results
                            except:
                                pass
                    except:
                        pass
                        
                if len(items) > 0: break

            seen_urls = set()

            for item in items:
                try:
                    info = []

                    url = str(item)
                    url = client.replaceHTMLCodes(url)
                    url = url.encode('utf-8')

                    if url in seen_urls: continue
                    seen_urls.add(url)

                    host = url.replace("\\", "")
                    host2 = host.strip('"')
                    host = re.findall('([\w]+[.][\w]+)$', urlparse.urlparse(host2.strip().lower()).netloc)[0]

                    if not host in hostDict: raise Exception()
                    if any(x in host2 for x in ['.rar', '.zip', '.iso']): continue

                    if '720p' in host2:
                        quality = 'HD'
                    elif '1080p' in host2:
                        quality = '1080p'
                    else:
                        quality = 'SD'

                    info = ' | '.join(info)
                    host = client.replaceHTMLCodes(host)
                    host = host.encode('utf-8')
                    sources.append({'source': host, 'quality': quality, 'language': 'en', 'url': host2, 'info': info, 'direct': False, 'debridonly': True})
                    # why is this hardcoded to debridonly=True? seems like overkill but maybe there's a resource-management reason?
                except:
                    pass
            check = [i for i in sources if not i['quality'] == 'CAM']
            if check: sources = check
            return sources
        except:
            failure = traceback.format_exc()
            log_utils.log('RLSBB - Exception: \n' + str(failure))
            return sources
    
    def search(self, querys):
        i = 0
        result = None
        while result == None and i < len(querys):

            q = re.sub('(\\\|/| -|:|;|\*|\?|"|\'|<|>|\|)', '', querys[i])
            q = q.replace("  ", " ").replace(" ", "-")
            log_utils.log("query : " + q)
                    
            result = client.request(self.base_link + q)

            if (result == None):
                log_utils.log("test " + str(i) + " = None - trying test " + str(i+1))
                i += 1
            else:
                log_utils.log("test " + str(i) + " Ok :" + str(len(result)))

        return result

    def resolve(self, url):
        return url
