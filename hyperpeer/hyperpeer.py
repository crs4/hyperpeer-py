# -*- coding: utf-8 -*-
"""
Created on Mon Feb  11 16:00:00 2019

@author: Jose F. Saenz-Cogollo

"""
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

logging.basicConfig(level=logging.INFO)

class PeerState(Enum):
    """
    `Enum` class that represents the possible states of a [Peer](#peer) instance.

    # Attributes
    STARTING (enum): connecting to signaling server.
    ONLINE (enum): connected to signaling server but not paired to any peer.
    LISTENING (enum): pairing and establishing a WebRTC connection with peer.
    CONNECTING (enum): WebRTC peer connection and data channel are ready.
    CONNECTED (enum): closing peer connection.
    DISCONNECTING (enum): waiting for incoming connections.
    CLOSING (enum): disconnecting from signaling server.
    CLOSED (enum): disconnected from signaling server and not longer usable.
    """
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
            raise TypeError('frame_generator should be a generator function')
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
        if not inspect.isfunction(frame_consumer):
            raise TypeError(
                'frame_consumer should be a function')
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
            self.consumer(frame)

class Peer:
    """
    The Peer class represents the local peer in a WebRTC application based on Hyperpeer. 
    It manages both the Websocket connection with the signaling server and the peer-to-peer communication via WebRTC with remote peers.
    
    # Attributes
    id (string): id of the instance.
    readyState (PeerState): State of the peer instance. It may have one of the values specified in the class [PeerState](#peerstate).

    # Arguments
    server_address (str): URL of the Hyperpeer signaling server, it should include the protocol prefix *ws://* or *wss://* that specify the websocket protocol to use.
    peer_type (str): Peer type. It can be used by other peers to know the role of the peer in the current application.
    id (str): Peer unique identification string. Must be unique among all connected peers. If it's undefined or null, the server will assign a random string.
    key (str): Peer validation string. It may be used by the server to verify the peer.
    media_source (str): Path or URL of the media source or file.
    media_source_format (str): Specific format of the media source. Defaults to autodect.
    media_sink (str): Path or filename to write with incoming video.
    frame_generator (function): Generator function that produces video frames as [NumPy arrays](https://docs.scipy.org/doc/numpy/reference/arrays.html) with [sRGB format](https://en.wikipedia.org/wiki/SRGB) with 24 bits per pixel (8 bits for each color). It should use the `yield` statement to generate arrays with elements of type `uint8` and with shape (vertical-resolution, horizontal-resolution, 3).
    frame_consumer (function): Function used to consume incoming video frames as [NumPy arrays](https://docs.scipy.org/doc/numpy/reference/arrays.html) with [sRGB format](https://en.wikipedia.org/wiki/SRGB) with 24 bits per pixel (8 bits for each color). It should receive an argument called `frame` which will be a NumPy array with elements of type `uint8` and with shape (vertical-resolution, horizontal-resolution, 3).
    ssl_context (ssl.SSLContext): Oject used to manage SSL settings and certificates in the connection with the signaling server when using wss. See [ssl documentation](https://docs.python.org/3/library/ssl.html?highlight=ssl.sslcontext#ssl.SSLContext) for more details. 
    datachannel_options (dict): Dictionary with the following keys: *label*, *maxPacketLifeTime*, *maxRetransmits*, *ordered*, and *protocol*. See the [documentation of *RTCPeerConnection.createDataChannel()*](https://developer.mozilla.org/en-US/docs/Web/API/RTCPeerConnection/createDataChannel#RTCDataChannelInit_dictionary) method of the WebRTC API for more details.

    # Example
    ```python
    from hyperpeer import Peer, PeerState
    import asyncio
    import numpy

    # Function used to generate video frames. It simply produce random images.
    def video_frame_generator():
        while True:
            frame = numpy.random.rand(720, 1280, 3)
            frame = numpy.uint8(frame * 100)
            yield frame

    # Frame counter
    received_frames = 0

    # Function used for consuming incoming video frames. It simply counts frames.
    def video_frame_consumer(frame):
        global received_frames
        received_frames += 1

    # Function used to consume incoming data. It simply print messages.
    def on_data(data):
        print('Remote message:')
        print(data)

    # Data channel settings. It sets the values for maximun throughout using UDP.
    datachannel_options = {
        'label': 'data_channel',
        'maxPacketLifeTime': None,
        'maxRetransmits': 0,
        'ordered': False,
        'protocol': ''
    }

    # Instanciate peer
    peer = Peer('wss://localhost:8080', peer_type='media-server', id='server1', frame_generator=video_frame_generator, frame_consumer=video_frame_consumer, ssl_context=ssl_context, datachannel_options=datachannel_options)

    # Coroutine used to produce and send data to remote peer. It simply send the value of the frame counter 10 times per second.
    async def sender():
        global peer
        global received_frames
        while peer.readyState == PeerState.CONNECTED:
            data = { 'received_frames': received_frames }
            await peer.send(data)
            await asyncio.sleep(0.1)
    
    # Main loop
    async def main():
        # Open server connection
        await peer.open()
        # Add data handler
        peer.add_data_handler(on_data)
        # List connected peers
        peers = await peer.get_peers()
        print(peers) # [{'id': 'server1', 'type': 'media-server', 'busy': False}, ... ]
        
        try:
            while True:
                global received_frames
                received_frames = 0
                # Wait for incoming connections
                remotePeerId = await peer.listen_connections()
                # Accept incoming connection
                await peer.accept_connection()
                # Send data while connected
                await sender()
                # If still disconnecting wait to be online to start over again
                while peer.readyState != PeerState.ONLINE:
                    await asyncio.sleep(1)
        except Exception as err:
            print(err)
            raise
        finally:
            # Close connection before leaving
            await peer.close()

    # Run main loop
    asyncio.run(main())
    ```
    """
    def __init__(self, serverAddress, peer_type='media-server', id=None, key=None, media_source=None, media_sink=None, 
                 frame_generator=None, frame_consumer=None, ssl_context=None, datachannel_options=None, media_source_format=None):
        self.url = serverAddress + '/' + peer_type
        if id:
           self.url += '/' + id
        if key:
            self.url += '/' + key
        self.id = str(id)
        self._ws = None
        self._pc = None
        self.readyState = PeerState.STARTING
        self._datachannel =  None
        self._handle_candidates_task = None
        self._data = None
        self._data_handlers = []
        self._frame_generator = frame_generator
        if frame_consumer:
            self._frame_consumer_feeder = FrameConsumerFeeder(frame_consumer)
        else:
            self._frame_consumer_feeder = None
        self._track_consumer_task = None
        self._ssl_context = ssl_context
        self._remote_track_monitor_task = None
        self._datachannel_options = datachannel_options
        if media_source != None:
            if media_source == '':
                raise Exception('Empty media source path!')
            else:
                try:
                    MediaPlayer(media_source)
                except Exception as av_error:
                    logging.exception('Media source error: ' + str(av_error))
                    raise
        self._media_source = media_source
        self._media_source_format = media_source_format        
    
    def _set_readyState(self, new_state):
        """
        Change the value of `self.readyState`
        """
        self.readyState = new_state
        logging.info('Peer (%s) state is %s', self.id, self.readyState)
    
    async def open(self):
        """
        (*Coroutine*) Open the connection with the Hyperpeer signaling server.

        It returns when the Websocket connection with the signaling server is established.          
        """
        if self._ssl_context:
            self._ws = await websockets.connect(self.url, ssl=self._ssl_context)
        else:
            self._ws = await websockets.connect(self.url)
        self._set_readyState(PeerState.ONLINE)

    async def close(self):
        """
        (*Coroutine*) Close the connection with the signaling server and with any remote peer.

        It returns when both WebRTC peer connection and Websocket server connection are closed.
        """
        if self.readyState == PeerState.CLOSED:
            return
        if self.readyState == PeerState.CONNECTING or self.readyState == PeerState.CONNECTED:
            await self.disconnect()
        if self._ws:
            await self._ws.close()
        self._set_readyState(PeerState.CLOSED)

    async def _get_signal(self, timeout=None):
        """
        (*Coroutine*) Wait for a message from the signaling server.

        # Returns
        object: Signal received.
        """
        try:
            message = await asyncio.wait_for(self._ws.recv(), timeout)
        except asyncio.TimeoutError:
            raise Exception('Server not responding!')
        except websockets.exceptions.ConnectionClosed:
            raise Exception('Websocket connection closed while waiting for a signal')
        try:
            signal = json.loads(message)
        except:
            raise TypeError('Received an invalid json message signal')
        return signal
    
    async def _send(self, data):
        """
        (*Coroutine*) Send a message to the signaling server.
        """
        try:
            await self._ws.send(json.dumps(data))
        except websockets.exceptions.ConnectionClosed:
            raise Exception('Websocket connection closed while sending a signal')
    
    async def get_peers(self):
        """
        (*Coroutine*) Returns the list of peers currently connected to the signaling server.

        # Returns
        list: List of peers currently connected to the signaling server. Each peer is represented by a dictionary with the following keys: id(`str`), type(`str`), busy(`bool`).

        # Raises
        Exception: If `peer.readyState` is not `PeerState.ONLINE`
        """
        if self.readyState != PeerState.ONLINE:
            raise Exception('Not in ONLINE state!')

        await self._send({'type': 'listPeers'})
        signal = await self._get_signal(timeout=2.0)
        if signal['type'] != 'peers':
            raise Exception('Expected peers from server', signal)

        return signal['peers']
    
    async def connect_to(self, remote_peer_id):
        """
        (*Coroutine*) Request a peer-to-peer connection with a remote peer.

        # Arguments
        remote_peer_id (str): id of the remote peer to connect to.
        
        # Raises
        Exception: If `peer.readyState` is not `PeerState.ONLINE`
        Exception: If a peer with id equal to *remote_peer_id* do not exist.
        Exception: If remote peer is busy.
        """
        if self.readyState != PeerState.ONLINE:
            raise Exception('Not in ONLINE state!')
        
        await self._send({'type': 'pair', 'remotePeerId': remote_peer_id})
        signal = await self._get_signal(timeout=2.0)
        if signal['type'] == 'error':
            raise Exception(signal['message'])
        if signal['type'] != 'status':
            raise Exception('Expected status from server', signal)
        if signal['status'] != 'paired':
            raise Exception('Cannot pair with peer!')
        self._set_readyState(PeerState.CONNECTING)
        await self._negotiate(initiator=False)

    async def listen_connections(self):
        """
        (*Coroutine*) Wait for incoming connections. 
        
        It returns when a connection request is received setting `peer.readyState` as `PeerState.CONNECTING`

        # Raises
        Exception: If `peer.readyState` is not `PeerState.ONLINE`
        """
        if self.readyState != PeerState.ONLINE:
            raise Exception('Not in ONLINE state!')
        await self._send({'type': 'ready'})
        self._set_readyState(PeerState.LISTENING)
        while True:
            signal = await self._get_signal()
            if signal['type'] != 'status':
                logging.warning('Expected status from server' +  str(signal))
                continue
            if signal['status'] != 'paired':
                logging.warning('Expected paired status!')
                continue
            break
        self._set_readyState(PeerState.CONNECTING)
        return signal['remotePeerId']
    
    async def accept_connection(self):
        """
        (*Coroutine*) Accept an incoming connection from a remote peer. You should call to the #Peer.listen_connections method first.

        # Raises
        Exception: If `peer.readyState` is not `PeerState.CONNECTING`
        """
        if self.readyState != PeerState.CONNECTING:
            raise Exception('Not in CONNECTING state!')
        await self._negotiate(initiator=True)
    
    async def send(self, data):
        """
        (*Coroutine*) Send a message to the connected remote peer using the established WebRTC data channel.

        # Arguments
        data (object): Data to send. It should be a string, number, list, or dictionary in order to be JSON serialized.

        # Raises
        Exception: If `peer.readyState` is not `PeerState.CONNECTED`
        """
        if self.readyState != PeerState.CONNECTED:
            raise Exception('Not in CONNECTED state!')
        if self._datachannel.readyState == 'open':
            self._datachannel.send(json.dumps(data))
        
    async def recv(self):
        """
        (*Coroutine*) Wait until a message from the remote peer is received.

        # Returns
        object: Data received.

        # Raises
        Exception: If `peer.readyState` is not `PeerState.CONNECTED`
        """
        if self.readyState != PeerState.CONNECTED:
            raise Exception('Not in CONNECTED state!')
        while self._data == None:
            await asyncio.sleep(0.1)
        data = self._data
        self._data = None
        return data
    
    def add_data_handler(self, handler):
        """
        Adds a function to the list of handlers to call whenever data is received.

        # Arguments
        handler (function): A function that will be called with the an argument called 'data'. 
        """
        self._data_handlers.append(handler)

    def remove_data_handler(self, handler):
        """
        Removes a function from the list of data handlers.

        # Arguments
        handler (function): The function that will be removed.
        """
        self._data_handlers.remove(handler)
    
    async def _cancel_task(self, task):
        """
        (*Coroutine*) Cancel a running task and wait until it's successfully cancelled.
        """
        if task.done():
            error = task.exception()
            if not error:
                return
            if not isinstance(error, asyncio.CancelledError):
                logging.error("A task raised and exception: %s", str(error))
            return
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            return

    async def disconnect(self, error=None): 
        """
        (*Coroutine*) Terminate the WebRTC peer-to-peer connection with the remote peer.
        """
        if self.readyState != PeerState.CONNECTING and self.readyState != PeerState.CONNECTED:
            return
        self._set_readyState(PeerState.DISCONNECTING)
        logging.info('canceling tasks...')
        if self._track_consumer_task:
            await self._cancel_task(self._track_consumer_task)
        if self._handle_candidates_task:
            await self._cancel_task(self._handle_candidates_task)
        if self._remote_track_monitor_task:
            await self._cancel_task(self._remote_track_monitor_task)
        logging.info('closing peer connection...')
        await self._pc.close()
        if self._ws.open:
            self._set_readyState(PeerState.ONLINE)
        else:
            await self.close()
        logging.info('Disconected peer %s', self.id)
        if error:
            logging.error('Peer %s was disconnected because an error occurred: %s', self.id, str(error))
            if isinstance(error, Exception):
                await self.close()
                raise error

    async def _handle_ice_candidates(self):
        """
        (*Coroutine*) Coroutine that handle the ICE candidates negotiation.
        """
        while self.readyState == PeerState.CONNECTING or self.readyState == PeerState.CONNECTED:
            signal = await self._get_signal()
            if 'type' in signal:
                if signal['type'] == 'status' and signal['status'] == 'unpaired':
                    if self.readyState == PeerState.CONNECTED:
                        logging.info('unpaired received, disconnecting...')
                        await self.disconnect()
            elif 'candidate' in signal:
                logging.info('Got ice candidate:')
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
                logging.debug(candidate)
                self._pc.addIceCandidate(candidate)
            else:
                raise Exception('Received an unexpected signal: ', signal)

    async def _remote_track_monitor(self):
        """
        (*Coroutine*) Coroutine that monitor the execution of the frame consumer.
        """
        while self.readyState == PeerState.CONNECTED:
            if self._track_consumer_task.done():
                error = self._track_consumer_task.exception()
                if not isinstance(error, asyncio.CancelledError):
                    logging.error('Track consumer error: ' + str(error))
                    await self.disconnect(error)
            await asyncio.sleep(0.1)


    async def _negotiate(self, initiator):
        """
        (*Coroutine*) Handle the establishment of the WebRTC peer connection.
        """
        self._pc = RTCPeerConnection()

        def add_datachannel_listeners():
            """
            Set the listeners to handle data channel events
            """
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
            
            @self._datachannel.on('error')
            async def on_error(error):
                logging.error('Datachannel error: ' + str(error))
                await self.disconnect(error)

        @self._pc.on('track')
        def on_track(track):
            """
            Set the consumer or destination of the incomming video and audio tracks
            """
            logging.info('Track %s received' % track.kind)

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
            """
            Monitor the ICE connection state
            """
            logging.info('ICE connection state of peer (%s) is %s', self.id,
                  self._pc.iceConnectionState)  
            if self._pc.iceConnectionState == 'failed':
                await self.disconnect()
            elif self._pc.iceConnectionState == 'completed':
                self._set_readyState(PeerState.CONNECTED)
        
        # Add media tracks
        if self._media_source:
            if self._media_source_format:
                player = MediaPlayer(
                    self._media_source, format=self._media_source_format)
            else:
                player = MediaPlayer(self._media_source)
            if player.audio:
                self._pc.addTrack(player.audio)
            if player.video:
                self._pc.addTrack(player.video)
                logging.info('Video player track added')
        elif self._frame_generator:
            self._pc.addTrack(FrameGeneratorTrack(self._frame_generator))
            logging.info('Video frame generator track added')

        if initiator: 
            logging.info('Initiating peer connection...')
            do = self._datachannel_options
            if do:
                self._datachannel = self._pc.createDataChannel(do['label'], do['maxPacketLifeTime'], do['maxRetransmits'],
                                                           do['ordered'], do['protocol'])
            else: 
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
            logging.info('Waiting for peer connection...')
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
            
        logging.info('starting _handle_candidates_task...')
        self._handle_candidates_task = asyncio.create_task(self._handle_ice_candidates())
        while self.readyState == PeerState.CONNECTING:
            await asyncio.sleep(0.2)
        
        if self._track_consumer_task:
            logging.info('starting _remote_track_monitor_task...')
            self._remote_track_monitor_task = asyncio.create_task(
                self._remote_track_monitor())



        



        






    
