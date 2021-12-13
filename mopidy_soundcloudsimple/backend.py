import logging
import json
import pykka
import requests
from datetime import datetime
from mopidy.models import Ref, Track, Album, Image, Artist
from mopidy.backend import *

logger = logging.getLogger(__name__)
scs_uri = 'soundcloudsimple:'
scs_uri_root = scs_uri + 'root'
scs_uri_user = scs_uri + 'user'
scs_uri_stream = scs_uri + 'stream:'
sc_api = 'https://api-v2.soundcloud.com'
imageSelector = 't500x500.jpg'
limit = 100
myStreamLabel = '   My Stream'
defaultHeaders = {
    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.93 Safari/537.36'}


class SoundcloudSimpleBackend(pykka.ThreadingActor, Backend):
    uri_schemes = [u'soundcloudsimple']

    # used uris:
    # soundcloudsimple:root (shows entry point for stream and users followed
    # soundcloudsimple:user<userid> (shows tracks for a followed user)    
    # soundcloudsimple:stream: (shows personal stream)
    # soundcloudsimple:stream: http   (the track streaming url in the personal stream)
    # soundcloudsimple:http....... (the track streaming url)

    def __init__(self, config, audio):
        super(SoundcloudSimpleBackend, self).__init__()        
        self.library = SoundcloudSimpleLibrary(self, config)
        self.playback = SoundcloudSimplePlaybackProvider(
            audio=audio, backend=self)        


class SoundcloudSimpleLibrary(LibraryProvider):
    root_directory = Ref.directory(uri=scs_uri_root, name='SoundCloud')

    def __init__(self, backend, config):
        super(SoundcloudSimpleLibrary, self).__init__(backend)
        self.imageCache = {}
        self.trackCache = {}
        self.refCache = {}
        self.clientId = config['soundcloudsimple']['client_id']
        self.userId = config['soundcloudsimple']['user_id']
        self.lastRefresh = datetime.now()
        self.cacheTimeMin = 1440

    def browse(self, uri):
        refs = []
        now = datetime.now()
        minutesSinceLastLoad = round(abs(now - self.lastRefresh).seconds / 60)
        # cache one day
        if (minutesSinceLastLoad > self.cacheTimeMin):
            self.refresh('')
            self.lastRefresh = now
            logger.info("Clearing cache ... ")

        # root
        if uri == scs_uri_root:
            # try the cache first
            if uri in self.refCache and self.refCache[uri]:
                refs = self.refCache[uri]
            else:
                refs = self.loadRootAlbumRefs()    

        # stream
        elif uri == scs_uri_stream:
            # try the cache first
            if uri in self.refCache and self.refCache[uri]:
                refs = self.refCache[uri]
            else:
                refs = self.loadTrackRefsFromStream()    

        # user
        else:
            # try the cache first
            if uri in self.refCache and self.refCache[uri]:
                refs = self.refCache[uri]
            else:
                refs = self.loadTrackRefsFromUser(uri)

        return refs

    def loadRootAlbumRefs(self):
        refs = []
        # get the user details
        payload = {'client_id': self.clientId}

        r = requests.get(sc_api + '/users/' + self.userId,
                         params=payload, headers=defaultHeaders, timeout=10)
        jsono = json.loads(r.text)        
        # get stream node
        streamUri = scs_uri_stream
        ref = Ref.album(name=myStreamLabel, uri=streamUri)
        imguri = jsono['avatar_url']
        imguri = imguri.replace("large.jpg", imageSelector)
        self.imageCache[streamUri] = Image(uri=imguri)
        refs.append(ref)        

        # get followings
        logger.info("Loading followings for user " + self.userId)
        payload = {'client_id': self.clientId, 'limit': limit}
        r = requests.get(sc_api + '/users/' + self.userId + '/followings',
                         params=payload, headers=defaultHeaders, timeout=10)
        
        if r.status_code != 200:
            logger.warn("Got HTTP " + str(r.status_code))

        jsono = json.loads(r.text)

        for follow in jsono['collection']:
            followingUri = scs_uri_user + str(follow['id'])
            ref = Ref.album(name=follow['username'], uri=followingUri)
            imguri = follow['avatar_url']
            imguri = imguri.replace("large.jpg", imageSelector)
            self.imageCache[followingUri] = Image(uri=imguri)
            refs.append(ref)
        self.refCache[scs_uri_root] = refs
        return refs

    def loadTrackRefsFromStream(self):
        # get a copy of all our track ref's
        refsCopy = []
        rootRefs = self.browse(scs_uri_root)
        for rootRef in rootRefs:
            if rootRef.uri != scs_uri_stream:
                userTrackRefs = self.browse(rootRef.uri)
                refsCopy = refsCopy + userTrackRefs

        # sort this copy by date
        refsCopy.sort(key=lambda x: self.trackCache[x.uri].date, reverse=True)
        refs = []
        trackNo = 0
        for ref in refsCopy:
            originalUri = ref.uri
            newUri = scs_uri_stream + originalUri.lstrip(scs_uri)
            streamTrackRef = Ref.track(name=ref.name, uri=newUri)
            refs.append(streamTrackRef)
            # copy the Track with new URI and with new naming
            trackNo += 1        
            originalTrack = self.trackCache[originalUri]
            newName = str(trackNo).zfill(2) + ". " + originalTrack.name[4:]
            track = Track(uri=newUri, name=newName, album=originalTrack.album,
                          artists=originalTrack.artists, length=originalTrack.length, date=originalTrack.date)
            self.trackCache[newUri] = track
            # copy the image
            if originalUri in self.imageCache:
                self.imageCache[newUri] = self.imageCache[originalUri]

        # lets limit to 99 tracks. Should be enough
        return refs[:99]

    def loadTrackRefsFromUser(self, uri):
        userid = uri.strip(scs_uri_user)
        refs = []
        payload = {'limit': limit, 'client_id': self.clientId}
        r = requests.get(sc_api + '/users/' + userid + '/tracks',
                         params=payload, headers=defaultHeaders, timeout=10)
        logger.info("Loading tracks of user " + userid)
        jsono = json.loads(r.text)
        trackNo = 0
        for trackJSON in jsono['collection']:
            trackNo += 1
            streamUrl = self.getMediaFromJSON(trackJSON['media'])
            trackRef = self.getTrackRefFromJSON(streamUrl, trackJSON)
            refs.append(trackRef)
            track = self.getTrackFromJSON(trackJSON, trackNo, trackRef.uri)
            self.trackCache[trackRef.uri] = track
        self.refCache[uri] = refs
        return refs

    def getMediaFromJSON(self, media):
        for stream in media['transcodings']:
            preset = stream['format']['protocol']
            if preset == 'progressive':
                return stream['url'] + "?client_id=" + self.clientId

    def getTrackRefFromJSON(self, streamUrl, track):
        trackuri = scs_uri + streamUrl
        ref = Ref.track(name=track['title'], uri=trackuri)
        return ref

    def getTrackFromJSON(self, trackJSON, trackNo, trackuri):
        if (trackJSON['artwork_url']):
            artwork = trackJSON['artwork_url']
            artwork = artwork.replace("large.jpg", imageSelector)
            self.imageCache[trackuri] = Image(uri=artwork)
        album = Album(name=trackJSON['user']['username'])
        artist = Artist(uri='none', name=trackJSON['user']['username'])      
        dateString = trackJSON['created_at']
        # date information in JSON: "created_at":"2012-06-25T12:03:44Z"
        dateObj = datetime.strptime(dateString, '%Y-%m-%dT%H:%M:%SZ')
        dateStringMop = dateObj.strftime("%Y-%m-%d")
        track = Track(uri=trackuri, name=str(trackNo).zfill(2) + '. ' + trackJSON['title'], album=album, artists=[
                      artist], date=dateStringMop, length=trackJSON['duration'], track_no=trackNo)
        return track      

    def refresh(self, uri):
        logger.info("refreshing for uri: " + uri)
        if uri == '':
            # we need to flush everything
            self.refCache = {}
        else:
            self.refCache[uri] = None
        return

    def lookup(self, uri, uris=None):
        if uri in self.trackCache:
            track = self.trackCache[uri]
            return [track]
        else:
            return []

    def get_images(self, uris):      
        ret = {}
        for uri in uris:
            if uri in self.imageCache:
                img = self.imageCache[uri]
                if img is not None: 
                    ret[uri] = [img]
        return ret

    def search(self, query=None, uris=None, exact=False):
        return {}


class SoundcloudSimplePlaybackProvider(PlaybackProvider):
    def translate_uri(self, uri):
        streamUrl = uri.lstrip(scs_uri)
        streamUrl = streamUrl.lstrip(scs_uri_stream)
        r = requests.get(streamUrl, headers=defaultHeaders)
        jsono = json.loads(r.text)
        return jsono['url']