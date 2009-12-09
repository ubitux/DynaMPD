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

import mpd, optparse, sys, time, urllib, xml.dom.minidom

__author__ = 'ubitux'
__version__ = '0.2.2~dev'

class DynaMPD:

    _api_key = 'b25b959554ed76058ac220b7b2e0a026'
    _api_root_url = 'http://ws.audioscrobbler.com/2.0/'

    def __init__(self, mpd_client):
        self.mpd_client = mpd_client
        self.n_append = 3

    def get_a_selection(self, playing_artist, playing_track):
        playlist = self.mpd_client.playlist()
        selection = []

        self._log(':: Search similar track [%s - %s]' % (playing_artist, playing_track))

        doc = self._api_request({'method': 'track.getsimilar', 'artist': playing_artist, 'track': playing_track})
        for node in doc.getElementsByTagName('track'):
            for name in node.getElementsByTagName('name'):
                if name.parentNode == node:
                    title = name.firstChild.data.encode('utf-8', 'ignore')
                else:
                    artist = name.firstChild.data.encode('utf-8', 'ignore')

            files = self.mpd_client.search('artist', artist, 'title', title)
            if not files:
                continue

            file = files[0]['file']
            if file in playlist + selection:
                continue

            self._log('    --> %s' % file)
            selection.append(file)
            if len(selection) >= self.n_append:
                break

        if not selection:
            doc = self._api_request({'method': 'artist.getsimilar', 'artist': playing_artist})
            for node in doc.getElementsByTagName('artist'):
                artist = node.getElementsByTagName('name')[0].firstChild.data.encode('utf-8', 'ignore')

                files = self.mpd_client.search('artist', artist)
                if not files:
                    continue

                file = self._get_best_track(artist, playlist + selection, files)
                if not file:
                    continue

                self._log('    --> %s' % file)
                selection.append(file)
                if len(selection) >= self.n_append:
                    break

        self._log('')
        return selection

    def _api_request(self, data):
        url = self._api_root_url + '?api_key=' + self._api_key + '&' + urllib.urlencode(data)
        self._log('   [LastFM] request: %s | url: %s' % (data['method'], url))
        return xml.dom.minidom.parse(urllib.urlopen(url))

    def _get_best_track(self, artist, playlist, matching_files):
        doc = self._api_request({'method': 'artist.getTopTracks', 'artist': artist})
        for track in doc.getElementsByTagName('track'):
            title = track.getElementsByTagName('name')[0].firstChild.data.encode('utf-8', 'ignore')
            files = self.mpd_client.search('artist', artist, 'title', title)
            for f in files:
                file = f['file']
                if file not in playlist:
                    return file
        for f in matching_files:
            file = f['file']
            if file not in playlist:
                return file
        return None

    def _log(self, str):
        if self.mpd_client.verbose: print str


class Core(mpd.MPDClient):

    def _getopts(self):
        parser = optparse.OptionParser()
        parser.add_option('-a', '--host', dest='host', help='MPD host', default='localhost')
        parser.add_option('-n', '--password', dest='password', help='MPD password')
        parser.add_option('-p', '--port', dest='port', type='int', help='MPD port', default=6600)
        parser.add_option('-q', '--quiet', dest='verbose', action="store_false", help='Quiet mode', default=True)
        opts, args = parser.parse_args()
        return (opts.host, opts.password, opts.port, opts.verbose)

    def _is_worth_listening(self, elapsed_time, total_time):
        return (total_time - elapsed_time) < int(total_time * 0.8)

    def run(self):
        prev = (None, None)
        dynampd = DynaMPD(self)
        while True:
            state = self.status()['state']
            if state == 'play':
                elapsed = self.status()['time'].split(':')[0]
                currentsong = self.currentsong()
                (artist, title, duration) = (currentsong.get('artist'), currentsong.get('title'), currentsong.get('time').split(":")[0])
                iwl = self._is_worth_listening(int(elapsed), int(duration))
                if artist and title and prev != (artist, title) and iwl:
                    prev = (artist, title)
                    for file in dynampd.get_a_selection(artist, title):
                        self.add(file)
            time.sleep(5)

    def __init__(self):
        mpd.MPDClient.__init__(self)
        host, password, port, self.verbose = self._getopts()
        self.connect(host, port)
        if password:
            self.password(password)

if __name__ == '__main__':
    c = Core()
    c.run()
