import asyncio
from aiortc import RTCPeerConnection, RTCSessionDescription, VideoStreamTrack, RTCIceCandidate
from aiortc.contrib.media import MediaBlackhole, MediaPlayer, MediaRecorder
from av import VideoFrame
from aioice import Candidate
import websockets
import json
from enum import Enum, auto
import inspect
import time
import logging
#logging.basicConfig(level=logging.INFO)

class PeerState(Enum):
    STARTING = auto()
    ONLINE = auto()
    LISTENING = auto()
    CONNECTING = auto()
    CONNECTED = auto()
    DISCONNECTING = auto()
    CLOSING = auto()
    CLOSED = auto()


class FrameGeneratorTrack(VideoStreamTrack):
    def __init__(self, frame_generator):
        if not inspect.isgeneratorfunction(frame_generator):
            raise TypeError('frame_generator should be an asynchronous generator function')
        super().__init__()  # don't forget this!
        self.generator = frame_generator()
        self.last_time = time.time()

    async def recv(self):
        try:
            frame = next(self.generator)
        except Exception as err:
            logging.exception(err)
            raise
        video_frame = VideoFrame.from_ndarray(frame, format='bgr24')
        pts, time_base = await self.next_timestamp()
        video_frame.pts = pts
        video_frame.time_base = time_base
        #logging.debug(str(time.time()-self.last_time))
        self.last_time = time.time()
        return video_frame


class FrameConsumerFeeder:
    def __init__(self, frame_consumer):
        if not inspect.iscoroutinefunction(frame_consumer):
            raise TypeError(
                'frame_consumer should be a coroutine function')
        self.consumer = frame_consumer
        self.last_time = time.time()

    async def feed_with(self, track):
        while True:
            video_frame = await track.recv()
            frame = video_frame.to_ndarray(format='bgr24')
            pts = video_frame.pts
            time_base = video_frame.time_base
            #logging.debug(str(time.time()-self.last_time))
            self.last_time = time.time()
            await self.consumer(frame)

class Peer:
    def __init__(self, serverAddress, peer_type='media-server', id=None, key=None, media_source=None, media_sink=None, frame_generator=None, frame_consumer=None):
        self.url = 'ws://' + serverAddress + '/' + peer_type
        if id:
           self.url += '/' + id
        if key:
            self.url += '/' + key
        self.id = str(id)
        self._ws = None
        self._pc = None
        self._player = None
        self.readyState = PeerState.STARTING
        self._datachannel =  None
        self._handle_candidates_task = None
        self._data = None
        self._data_handlers = []
        if frame_generator:
            self._video_frame_track = FrameGeneratorTrack(frame_generator)
        else:
            self._video_frame_track = None
        if frame_consumer:
            self._frame_consumer_feeder = FrameConsumerFeeder(frame_consumer)
        else:
            self._frame_consumer_feeder = None
        self._track_consumer_task = None
    
    def _set_readyState(self, new_state):
        self.readyState = new_state
        logging.info('Peer (%s) state is %s', self.id, self.readyState)
    
    async def open(self):
        self._ws = await websockets.connect(self.url)
        self._set_readyState(PeerState.ONLINE)

    async def close(self):
        if self.readyState == PeerState.CLOSED:
            return
        if self.readyState == PeerState.CONNECTING or self.readyState == PeerState.CONNECTED:
            await self.disconnect()
        if self._ws:
            await self._ws.close()
        self._set_readyState(PeerState.CLOSED)

    async def _get_signal(self, timeout=None):
        if not self._ws.open:
            await self.close()
            raise Exception('Not connected!')
        try:
            message = await asyncio.wait_for(self._ws.recv(), timeout)
        except asyncio.TimeoutError:
            raise Exception('Server not responding!')
        try:
            signal = json.loads(message)
        except:
            raise TypeError('Received an invalid json message signal')
        return signal
    
    async def _send(self, data):
        if not self._ws.open:
            await self.close()
            raise Exception('Not connected!')
        await self._ws.send(json.dumps(data))
    
    async def get_peers(self):
        if self.readyState != PeerState.ONLINE:
            raise Exception('Not in ONLINE state!')

        await self._send({'type': 'listPeers'})
        signal = await self._get_signal(timeout=2.0)
        if signal['type'] != 'peers':
            raise Exception('Expected peers from server', signal)

        return signal['peers']
    
    async def connect_to(self, remote_peer_id):
        if self.readyState != PeerState.ONLINE:
            raise Exception('Not in ONLINE state!')
        
        await self._send({'type': 'pair', 'remotePeerId': remote_peer_id})
        signal = await self._get_signal(timeout=2.0)
        if signal['type'] != 'status':
            raise Exception('Expected status from server', signal)
        if signal['status'] != 'paired':
            raise Exception('Cannot pair with peer!')
        self._set_readyState(PeerState.CONNECTING)
        await self._negotiate(initiator=False)

    async def listen_connections(self):
        if self.readyState != PeerState.ONLINE:
            raise Exception('Not in ONLINE state!')
        self._set_readyState(PeerState.LISTENING)
        signal = await self._get_signal()
        if signal['type'] != 'status':
            raise Exception('Expected status from server', signal)
        if signal['status'] != 'paired':
            raise Exception('Expected paired status!')
        self._set_readyState(PeerState.CONNECTING)
    
    async def accept_connection(self):
        if self.readyState != PeerState.CONNECTING:
            raise Exception('Not in CONNECTING state!')
        await self._negotiate(initiator=True)
    
    async def send(self, data):
        if self.readyState != PeerState.CONNECTED:
            raise Exception('Not in CONNECTED state!')
        self._datachannel.send(json.dumps(data))
        
    async def recv(self):
        if self.readyState != PeerState.CONNECTED:
            raise Exception('Not in CONNECTED state!')
        while self._data == None:
            await asyncio.sleep(0.1)
        data = self._data
        self._data = None
        return data
    
    def add_data_handler(self, handler):
        self._data_handlers.append(handler)

    def remove_data_handler(self, handler):
        self._data_handlers.remove(handler)

    async def disconnect(self): 
        if self.readyState != PeerState.CONNECTING and self.readyState != PeerState.CONNECTED:
            return
        self._set_readyState(PeerState.DISCONNECTING)
        if self._track_consumer_task:
            self._track_consumer_task.cancel()
            try:
                await self._track_consumer_task
            except asyncio.CancelledError:
                logging.info("_track_consumer_task is cancelled now")
        if self._handle_candidates_task:
            self._handle_candidates_task.cancel()
            try:
                await self._handle_candidates_task
            except asyncio.CancelledError:
                logging.info("_handle_candidates_task is cancelled now")
        await self._pc.close()
        if self._ws.open:
            self._set_readyState(PeerState.ONLINE)
        else:
            await self.close()
        logging.info('Disconected peer %s', self.id)

    async def _handle_ice_candidates(self):
        while True:
            signal = await self._get_signal()
            if signal['type']:
                if signal['type'] == 'status' and signal['status'] == 'unpaired':
                    self.disconnect()
            elif signal['candidate']:
                logging.debug('Got ice candidate:')
                candi = Candidate.from_sdp(signal['candidate']['candidate'])
                candidate = RTCIceCandidate(
                    component=candi.component,
                    foundation=candi.foundation,
                    ip=candi.host,
                    port=candi.port,
                    priority=candi.priority,
                    protocol=candi.transport,
                    relatedAddress=candi.related_address,
                    relatedPort=candi.related_port,
                    tcpType=candi.tcptype,
                    type=candi.type,
                    sdpMLineIndex=signal['candidate']['sdpMLineIndex'],
                    sdpMid=signal['candidate']['sdpMid'])
                self._pc.addIceCandidate(candidate)
            else:
                raise Exception('Received an unexpected signal: ', signal)

    async def _negotiate(self, initiator):
        self._pc = RTCPeerConnection()
        def add_datachannel_listeners():
            @self._datachannel.on('message')
            def on_message(message):
                try:
                    data = json.loads(message)
                except:
                    raise TypeError('Received an invalid json message data')
                self._data = data
                for handler in self._data_handlers:
                    handler(data)

            @self._datachannel.on('close')
            async def on_close():
                if self.readyState == PeerState.CONNECTED:
                    logging.info('Datachannel lost, disconnecting...') 
                    await self.disconnect()

        @self._pc.on('track')
        def on_track(track):
            print('Track %s received' % track.kind)

            if track.kind == 'audio':
                #webrtc_connection.addTrack(player.audio)
                #recorder.addTrack(track)
                pass
            elif track.kind == 'video':
                #local_video = VideoTransformTrack(track, transform=signal['video_transform'])
                #webrtc_connection.addTrack(local_video)
                if self._frame_consumer_feeder:
                    self._track_consumer_task = asyncio.create_task(
                        self._frame_consumer_feeder.feed_with(track))

            @track.on('ended')
            async def on_ended():
                logging.info('Track %s ended' % track.kind)
                #await recorder.stop()

        @self._pc.on('iceconnectionstatechange')
        async def on_iceconnectionstatechange():
            logging.info('ICE connection state of peer (%s) is %s', self.id,
                  self._pc.iceConnectionState)  
            if self._pc.iceConnectionState == 'failed':
                await self.disconnect()
            elif self._pc.iceConnectionState == 'completed':
                self._set_readyState(PeerState.CONNECTED)

        if self._player:
            if self._player.audio:
                self._pc.addTrack(self._player.audio)
            if self._player.video:
                self._pc.addTrack(self._player.video)
        elif self._video_frame_track:
            self._pc.addTrack(self._video_frame_track)


        if initiator:   
            self._datachannel = self._pc.createDataChannel('data_channel')
            await self._pc.setLocalDescription(await self._pc.createOffer())
            signal = {
                'sdp': self._pc.localDescription.sdp,
                'type': self._pc.localDescription.type
            }
            await self._send(signal)
            signal = await self._get_signal()
            if signal['type'] != 'answer':
                raise Exception('Expected answer from remote peer', signal)
            answer = RTCSessionDescription(
                sdp=signal['sdp'],
                type=signal['type'])
            await self._pc.setRemoteDescription(answer)

            @self._datachannel.on('open')
            def on_open():
                self._set_readyState(PeerState.CONNECTED)
                add_datachannel_listeners()
                pass#asyncio.ensure_future(send_pings())
        else: 
            @self._pc.on('datachannel')
            async def on_datachannel(channel):
                self._datachannel = channel
                self._set_readyState(PeerState.CONNECTED)
                add_datachannel_listeners()

            signal = await self._get_signal()
            if signal['type'] != 'offer':
                raise Exception('Expected offer from remote peer', signal)
            offer = RTCSessionDescription(
                sdp=signal['sdp'],
                type=signal['type'])
            await self._pc.setRemoteDescription(offer)
            answer = await self._pc.createAnswer()
            await self._pc.setLocalDescription(answer)
            answer = {
                'sdp': self._pc.localDescription.sdp,
                'type': self._pc.localDescription.type
            }
            await self._send(answer)
            

        self._handle_candidates_task = asyncio.create_task(self._handle_ice_candidates())
        while self.readyState == PeerState.CONNECTING:
            await asyncio.sleep(0.2)
        return



        



        






    
