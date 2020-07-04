import logging
import json
import pykka
import requests
from mopidy.models import Ref,Track,Album,Image,Artist
from mopidy.backend import *

logger = logging.getLogger(__name__)
scs_uri='soundcloudsimple:'
scs_uri_root=scs_uri+'root'
scs_uri_user=scs_uri+'user'
scs_uri_stream=scs_uri+'stream'
sc_api='https://api-v2.soundcloud.com'

class SoundcloudSimpleBackend(pykka.ThreadingActor, Backend):
    uri_schemes = [u'soundcloudsimple']
 
    def __init__(self, config, audio):
        super(SoundcloudSimpleBackend, self).__init__()        
        self.library = SoundcloudSimpleLibrary(self,config)
        self.playback = SoundcloudSimplePlaybackProvider(audio=audio, backend=self)        
        
class SoundcloudSimpleLibrary(LibraryProvider):
    root_directory = Ref.directory(uri=scs_uri_root, name='SoundCloud')
    
    def __init__(self, backend, config):
        super(SoundcloudSimpleLibrary, self).__init__(backend)
        self.imageCache = {}
        self.trackCache = {}
        self.auth_token = config['soundcloudsimple']['auth_token']
        self.clientId = config['soundcloudsimple']['client_id']
 
    def browse(self, uri):    
      refs=[]
      if uri==scs_uri_root:
        # get the user id
        payload = {'oauth_token': self.auth_token}
        r =requests.get(sc_api + '/me', params=payload, timeout=10)
        jsono = json.loads(r.text)
        userid = jsono['id']
        
        # get stream
        streamUri = scs_uri_stream
        ref = Ref.album(name='_Stream', uri=streamUri)
        imguri = jsono['avatar_url']
        imguri = imguri.replace("large.jpg", "t500x500.jpg")
        self.imageCache[streamUri] = Image(uri=imguri)
        refs.append(ref)        
        
        # get followings
        r =requests.get(sc_api + '/users/' + str(userid) + '/followings', params=payload, timeout=10)
        jsono = json.loads(r.text)
        for follow in jsono['collection']:
          followingUri = scs_uri_user + str(follow['id'])
          ref = Ref.album(name=follow['username'], uri=followingUri)
          imguri = follow['avatar_url']
          imguri = imguri.replace("large.jpg", "t500x500.jpg")
          self.imageCache[followingUri] = Image(uri=imguri)
          refs.append(ref)

      elif uri==scs_uri_stream:
        payload = {'limit': '100', 'oauth_token': self.auth_token}
        r =requests.get(sc_api + '/stream', params=payload, timeout=10)
        jsono = json.loads(r.text)
        trackNo = 0
        for p in jsono['collection']:
          if 'track' in p:
            trackNo += 1
            trackJSON = p['track']
            streamUrl = self.getMediaFromJSON(trackJSON['media'])
            trackRef = self.getTrackRefFromJSON(streamUrl, trackJSON)
            refs.append(trackRef)
            track = self.getTrackFromJSON(trackJSON, trackNo, streamUrl)
            self.trackCache[trackRef.uri] = track
        
      else:
        account = uri.strip(scs_uri_user)
        payload = {'limit': '100', 'client_id': self.clientId}
        r =requests.get(sc_api + '/users/' + account + '/tracks', params=payload, timeout=10)
        jsono = json.loads(r.text)
        trackNo = 0
        for trackJSON in jsono['collection']:
          trackNo += 1
          streamUrl = self.getMediaFromJSON(trackJSON['media'])
          trackRef = self.getTrackRefFromJSON(streamUrl, trackJSON)
          refs.append(trackRef)
          track = self.getTrackFromJSON(trackJSON, trackNo, trackRef.uri)
          self.trackCache[trackRef.uri] = track

      return refs

    def getMediaFromJSON(self, media):
      for stream in media['transcodings']:
        preset = stream['format']['protocol']
        if preset == 'progressive':
          return stream['url']

    def getTrackRefFromJSON(self, streamUrl, track):
      trackuri=scs_uri + streamUrl + "?client_id=" + self.clientId
      ref=Ref.track(name=track['title'], uri=trackuri)
      return ref

    def getTrackFromJSON(self, trackJSON, trackNo, trackuri):
      if (trackJSON['artwork_url']):
        artwork = trackJSON['artwork_url']
        artwork = artwork.replace("large.jpg", "t500x500.jpg")
        self.imageCache[trackuri] = Image(uri=artwork)
      album = Album(name=trackJSON['user']['username'])
      artist = Artist(uri='none',name=trackJSON['user']['username'])
      track=Track(uri=trackuri,name=str(trackNo).zfill(2) + '. ' + trackJSON['title'],album=album,artists=[artist],length=trackJSON['duration'],track_no=trackNo)
      return track
      
      
    def refresh(self, uri=None):
      self.imageCache = {}
      self.trackCache = {}
      return

    def lookup(self, uri, uris=None):
      logger.info("lookup: " + uri)
      if uri in self.trackCache:
        track=self.trackCache[uri]
        return [track]
      else:
        return []

    def get_images(self, uris):      
      ret={}
      for uri in uris:
        if uri in self.imageCache:
          img=self.imageCache[uri]
          if img is not None: 
            ret[uri]=[img]
      return ret

    def search(self, query=None, uris=None, exact=False):
      return {}

class SoundcloudSimplePlaybackProvider(PlaybackProvider):
    def translate_uri(self, uri):
      streamUrl = uri.lstrip(scs_uri)
      r =requests.get(streamUrl)
      jsono = json.loads(r.text)
      return jsono['url']
