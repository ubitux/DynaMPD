#!/usr/bin/env python
# -*- coding: utf-8 -*-

#
# DO WHAT THE FUCK YOU WANT TO PUBLIC LICENSE
#                     Version 2, December 2004
#
#  Copyright (C) 2009 ubitux
#  Everyone is permitted to copy and distribute verbatim or modified
#  copies of this license document, and changing it is allowed as long
#  as the name is changed.
#
#             DO WHAT THE FUCK YOU WANT TO PUBLIC LICENSE
#    TERMS AND CONDITIONS FOR COPYING, DISTRIBUTION AND MODIFICATION
#
#   0. You just DO WHAT THE FUCK YOU WANT TO.
#

import mpd, time, urllib, xml.dom.minidom, re
from xml.parsers.expat import ExpatError as ParseError

__author__ = 'ubitux and Amak'
__version__ = '0.4.0~dev'

class DynaMPD:

    _api_key = 'b25b959554ed76058ac220b7b2e0a026'
    _api_root_url = 'http://ws.audioscrobbler.com/2.0/'

    def __init__(self, mpd_client):
        self.mpd_client = mpd_client
        self.max_selection_len = mpd_client.max_songs

    def get_a_selection(self, playing_artist, playing_track):

        def sel_ok(selection):
            self._log('')
            return selection

        def split_artists(artists):
            return [artists] + [a.strip() for a in re.split(r'(?i),|feat[^ ]*|&', artists)]

        playlist = self.mpd_client.playlist()
        selection = []

        self._log(':: Search similar track [%s - %s]' % (playing_artist, playing_track))

        doc = self._api_request({'method': 'track.getsimilar', 'artist': playing_artist, 'track': playing_track})
        for node in doc.getElementsByTagName('track'):

            title, artist = None, None
            for name in node.getElementsByTagName('name'):
                if name.parentNode == node:
                    title = name.firstChild.data.encode('utf-8', 'ignore')
                else:
                    artist = name.firstChild.data.encode('utf-8', 'ignore')
            if None in (title, artist):
                continue

            songs = self.mpd_client.search('artist', artist, 'title', title)
            if self._add_one_song_to_selection(songs, playlist, selection) >= self.max_selection_len:
                return sel_ok(selection)

        for sub_artist in split_artists(playing_artist):
            doc = self._api_request({'method': 'artist.getsimilar', 'artist': sub_artist})
            for node in doc.getElementsByTagName('artist'):
                artist = node.getElementsByTagName('name')[0].firstChild.data.encode('utf-8', 'ignore')

                if not self.mpd_client.search('artist', artist):
                    self._log('No artist matching [%s] in database' % artist)
                    continue

                doc_toptracks = self._api_request({'method': 'artist.getTopTracks', 'artist': artist})
                track = doc_toptracks.getElementsByTagName('track')[0]
                title = track.getElementsByTagName('name')[0].firstChild.data.encode('utf-8', 'ignore')
                songs = self.mpd_client.search('artist', artist, 'title', title)
                if self._add_one_song_to_selection(songs, playlist, selection) >= self.max_selection_len:
                    return sel_ok(selection)

        return sel_ok(selection)

    def _add_one_song_to_selection(self, songs, playlist, selection):
        sel_len = len(selection)
        if not songs:
            return sel_len
        for song in songs:
            fname = song['file']
            if fname not in playlist + selection:


                self._log('    → %s' % fname)
                selection.append(fname)
                return sel_len + 1
        return sel_len

    def _api_request(self, data):
        url = self._api_root_url + '?api_key=' + self._api_key + '&' + urllib.urlencode(data)
        self._log('   [LastFM] request: %s | url: %s' % (data['method'], url))
        return xml.dom.minidom.parse(urllib.urlopen(url))

    def _log(self, msg):
        if self.mpd_client.verbose:
            print msg

class Core(mpd.MPDClient):

    _config_file = '~/.config/dynampd.conf'

    def __init__(self):

        def getopts():
            import os, optparse, ConfigParser
            from StringIO import StringIO

            config = ConfigParser.RawConfigParser()
            cfile = open(os.path.expanduser(self._config_file), 'r')
            config.readfp(StringIO('[s]\n' + cfile.read()))
            cfg_host  = config.get('s', 'host')         if config.has_option('s', 'host')       else 'localhost'
            cfg_pass  = config.get('s', 'password')     if config.has_option('s', 'password')   else None
            cfg_port  = config.getint('s', 'port')      if config.has_option('s', 'port')       else 6600
            cfg_quiet = config.getboolean('s', 'quiet') if config.has_option('s', 'quiet')      else False
            cfg_msong = config.getint('s', 'max_songs') if config.has_option('s', 'max_songs')  else 3
            cfg_wait  = config.getint('s', 'wait')      if config.has_option('s', 'wait')       else 20
            cfile.close()

            parser = optparse.OptionParser()
            parser.add_option('-a', '--host', dest='host', help='MPD host', default=cfg_host)
            parser.add_option('-n', '--password', dest='password', help='MPD password', default=cfg_pass)
            parser.add_option('-p', '--port', dest='port', type='int', help='MPD port', default=cfg_port)
            parser.add_option('-q', '--quiet', dest='verbose', action="store_false", help='Quiet mode', default=(not cfg_quiet))
            parser.add_option('-m', '--max-songs', dest='max_songs', type='int', help='Maximum songs to append each time', default=cfg_msong)
            parser.add_option('-w', '--wait', dest='wait', type='int', help='Percent of current song length to wait before requesting new songs', default=cfg_wait)
            opts, _ = parser.parse_args()
            return (opts.host, opts.password, opts.port, opts.verbose, opts.max_songs, opts.wait)

        mpd.MPDClient.__init__(self)
        host, password, port, self.verbose, self.max_songs, self.wait = getopts()
        self.connect(host, port)
        if password:
            self.password(password)

    def run(self):

        def is_worth_listening(elapsed_time, total_time):
            return (total_time - elapsed_time) < int(total_time * (100 - self.wait) / 100.)

        prev = (None, None)
        dynampd = DynaMPD(self)
        try:
            while True:
                state = self.status()['state']
                if state == 'play':
                    elapsed = self.status()['time'].split(':')[0]
                    currentsong = self.currentsong()
                    (artist, title, duration) = (currentsong.get('artist'), currentsong.get('title'), currentsong.get('time').split(":")[0])
                    if artist and title and prev != (artist, title) and is_worth_listening(int(elapsed), int(duration)):
                        prev = (artist, title)
                        try:
                            for fname in dynampd.get_a_selection(artist, title):
                                self.add(fname)
                        except ParseError:
                            prev = (None, None)
                            print 'Error: unable to parse Last.FM DOM. retry in 5 seconds'
                time.sleep(5)
        except KeyboardInterrupt:
            if self.verbose:
                print 'Dynampd %s is now quitting...' % (__version__ )

if __name__ == '__main__':
    Core().run()
