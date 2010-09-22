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

import mpd, optparse, time, urllib, xml.dom.minidom
from xml.parsers.expat import ExpatError as ParseError

__author__ = 'ubitux and Amak'
__version__ = '0.4.0~dev'

class DynaMPD:

    _api_key = 'b25b959554ed76058ac220b7b2e0a026'
    _api_root_url = 'http://ws.audioscrobbler.com/2.0/'
    _max_selection_len = 3

    def __init__(self, mpd_client):
        self.mpd_client = mpd_client

    def get_a_selection(self, playing_artist, playing_track):

        def sel_ok(selection):
            self._log('')
            return selection

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
            if self._add_one_song_to_selection(songs, playlist, selection) >= self._max_selection_len:
                return sel_ok(selection)

        doc = self._api_request({'method': 'artist.getsimilar', 'artist': playing_artist})
        for node in doc.getElementsByTagName('artist'):
            artist = node.getElementsByTagName('name')[0].firstChild.data.encode('utf-8', 'ignore')

            if not self.mpd_client.search('artist', artist):
                self._log('No artist matching [%s] in database' % artist)
                continue

            doc_toptracks = self._api_request({'method': 'artist.getTopTracks', 'artist': artist})
            track = doc_toptracks.getElementsByTagName('track')[0]
            title = track.getElementsByTagName('name')[0].firstChild.data.encode('utf-8', 'ignore')
            songs = self.mpd_client.search('artist', artist, 'title', title)
            if self._add_one_song_to_selection(songs, playlist, selection) >= self._max_selection_len:
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

    def __init__(self):

        def getopts():
            parser = optparse.OptionParser()
            parser.add_option('-a', '--host', dest='host', help='MPD host', default='localhost')
            parser.add_option('-n', '--password', dest='password', help='MPD password')
            parser.add_option('-p', '--port', dest='port', type='int', help='MPD port', default=6600)
            parser.add_option('-q', '--quiet', dest='verbose', action="store_false", help='Quiet mode', default=True)
            opts, _ = parser.parse_args()
            return (opts.host, opts.password, opts.port, opts.verbose)

        mpd.MPDClient.__init__(self)
        host, password, port, self.verbose = getopts()
        self.connect(host, port)
        if password:
            self.password(password)

    def run(self):

        def is_worth_listening(elapsed_time, total_time):
            return (total_time - elapsed_time) < int(total_time * 0.8)

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
