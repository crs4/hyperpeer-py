# hyperpeer-py 
hyperpeer-py is the python module for implementing media servers or backend peers in applications based on Hyperpeer. This module provides a class called [Peer](#Peer) which manages both the connection with the signaling server and the peer-to-peer communication via WebRTC with remote peers. It also provides an __Enum__ class called [PeerState](#peerstate) that defines the possible states of a [Peer](#peer) instance. 

# Features

 - Built on top of [**asyncio**](https://docs.python.org/3/library/asyncio.html?highlight=asyncio#module-asyncio), Python’s standard asynchronous I/O framework. 
 - Based on the popular modules [aiortc](https://aiortc.readthedocs.io/en/latest/) 
 and [websockets](https://websockets.readthedocs.io/en/stable/). 

# API Reference


# Peer
```python
Peer(self, serverAddress, peer_type='media-server', id=None, key=None, media_source=None, media_sink=None, frame_generator=None, frame_consumer=None, frame_rate=30, ssl_context=None, datachannel_options=None, media_source_format=None)
```

The Peer class represents the local peer in a WebRTC application based on Hyperpeer.
It manages both the Websocket connection with the signaling server and the peer-to-peer communication via WebRTC with remote peers.

__Attributes__

- `id (string)`: id of the instance.
- `readyState (PeerState)`: State of the peer instance. It may have one of the values specified in the class [PeerState](#peerstate).

__Arguments__

- __server_address (str)__: URL of the Hyperpeer signaling server, it should include the protocol prefix *ws://* or *wss://* that specify the websocket protocol to use.
- __peer_type (str)__: Peer type. It can be used by other peers to know the role of the peer in the current application.
- __id (str)__: Peer unique identification string. Must be unique among all connected peers. If it's undefined or null, the server will assign a random string.
- __key (str)__: Peer validation string. It may be used by the server to verify the peer.
- __media_source (str)__: Path or URL of the media source or file.
- __media_source_format (str)__: Specific format of the media source. Defaults to autodect.
- __media_sink (str)__: Path or filename to write with incoming video.
- __frame_generator (generator function)__: Generator function that produces video frames as [NumPy arrays](https://docs.scipy.org/doc/numpy/reference/arrays.html) with [sRGB format](https://en.wikipedia.org/wiki/SRGB) with 24 bits per pixel (8 bits for each color). It should use the `yield` statement to generate arrays with elements of type `uint8` and with shape (vertical-resolution, horizontal-resolution, 3). Frame rate is automatically managed to match __frame_rate__.
- __frame_consumer (function)__: Function used to consume incoming video frames as [NumPy arrays](https://docs.scipy.org/doc/numpy/reference/arrays.html) with [sRGB format](https://en.wikipedia.org/wiki/SRGB) with 24 bits per pixel (8 bits for each color). It should receive an argument called `frame` which will be a NumPy array with elements of type `uint8` and with shape (vertical-resolution, horizontal-resolution, 3).
- __frame_rate (int)__: Streaming frame rate.
- __ssl_context (ssl.SSLContext)__: Oject used to manage SSL settings and certificates in the connection with the signaling server when using wss. See [ssl documentation](https://docs.python.org/3/library/ssl.html?highlight=ssl.sslcontext#ssl.SSLContext) for more details.
- __datachannel_options (dict)__: Dictionary with the following keys: *label*, *maxPacketLifeTime*, *maxRetransmits*, *ordered*, and *protocol*. See the [documentation of *RTCPeerConnection.createDataChannel()*](https://developer.mozilla.org/en-US/docs/Web/API/RTCPeerConnection/createDataChannel#RTCDataChannelInit_dictionary) method of the WebRTC API for more details.

__Example__

```python
from hyperpeer import Peer, PeerState
import asyncio
import numpy

# Frame counter
received_frames = 0

def video_frame_consumer(frame):
    """ Function used for consuming incoming video frames. It simply counts frames
    
    Arguments:
        frame {ndarray} -- Video frame as a NumPy array with sRGB format, elements of type `uint8` and with shape (vertical-resolution, horizontal-resolution, 3)
    """    
    global received_frames
    received_frames += 1

def video_frame_generator():
    """ Generator Function used to generate video frames. It simply produce random images.
    
    Yields:
        ndarray -- It should be a NumPy array with sRGB format, elements of type `uint8` and with shape (vertical-resolution, horizontal-resolution, 3)
    """    
    while True:
        frame = numpy.random.rand(720, 1280, 3)
        frame = numpy.uint8(frame * 100)
        yield frame

def on_data(data):
    """ Function used to consume incoming data. It simply print messages.
    
    Arguments:
        data {*} -- Incoming message. It can be any JSON serializable object.
    """    
    print('Remote message:')
    print(data)

# Instantiate peer
peer = Peer(
    server_address='ws://localhost:8080', 
    peer_type='my-worker', 
    id='worker1', 
    frame_consumer=video_frame_consumer,
    frame_generator=video_frame_generator)

async def sender():
    """ Coroutine used to produce and send data to remote peer. It simply send the value of the frame counter 10 times per second.
    """    
    global peer
    global received_frames
    while peer.readyState == PeerState.CONNECTED:
        data = { 'received_frames': received_frames }
        await peer.send(data)
        await asyncio.sleep(0.1)

async def main():
    """ Main loop
    """    
    # Open server connection
    await peer.open()

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
        # Close server connection before leaving
        await peer.close()

# Run main loop
asyncio.run(main())
```

## open
```python
Peer.open(self)
```

(*Coroutine*) Open the connection with the Hyperpeer signaling server.

It returns when the Websocket connection with the signaling server is established.

## close
```python
Peer.close(self)
```

(*Coroutine*) Close the connection with the signaling server and with any remote peer.

It returns when both WebRTC peer connection and Websocket server connection are closed.

## get_peers
```python
Peer.get_peers(self)
```

(*Coroutine*) Returns the list of peers currently connected to the signaling server.

__Returns__

`list`: List of peers currently connected to the signaling server. Each peer is represented by a dictionary with the following keys: id(`str`), type(`str`), busy(`bool`).

__Raises__

- `Exception`: If `peer.readyState` is not `PeerState.ONLINE`

## connect_to
```python
Peer.connect_to(self, remote_peer_id)
```

(*Coroutine*) Request a peer-to-peer connection with a remote peer.

__Arguments__

- __remote_peer_id (str)__: id of the remote peer to connect to.

__Raises__

- `Exception`: If `peer.readyState` is not `PeerState.ONLINE`
- `Exception`: If a peer with id equal to *remote_peer_id* do not exist.
- `Exception`: If remote peer is busy.

## listen_connections
```python
Peer.listen_connections(self)
```

(*Coroutine*) Wait for incoming connections.

It returns when a connection request is received setting `peer.readyState` as `PeerState.CONNECTING`

__Raises__

- `Exception`: If `peer.readyState` is not `PeerState.ONLINE`

## accept_connection
```python
Peer.accept_connection(self)
```

(*Coroutine*) Accept an incoming connection from a remote peer. You should call to the `Peer.listen_connections` method first.

__Raises__

- `Exception`: If `peer.readyState` is not `PeerState.CONNECTING`

## send
```python
Peer.send(self, data)
```

(*Coroutine*) Send a message to the connected remote peer using the established WebRTC data channel.

__Arguments__

- __data (object)__: Data to send. It should be a string, number, list, or dictionary in order to be JSON serialized.

__Raises__

- `Exception`: If `peer.readyState` is not `PeerState.CONNECTED`

## recv
```python
Peer.recv(self)
```

(*Coroutine*) Wait until a message from the remote peer is received.

__Returns__

`object`: Data received.

__Raises__

- `Exception`: If `peer.readyState` is not `PeerState.CONNECTED`

## add_data_handler
```python
Peer.add_data_handler(self, handler)
```

Adds a function to the list of handlers to call whenever data is received.

__Arguments__

- __handler (function)__: A function that will be called with the an argument called 'data'.

## remove_data_handler
```python
Peer.remove_data_handler(self, handler)
```

Removes a function from the list of data handlers.

__Arguments__

- __handler (function)__: The function that will be removed.

## disconnect
```python
Peer.disconnect(self, error=None)
```

(*Coroutine*) Terminate the WebRTC peer-to-peer connection with the remote peer.

# PeerState
```python
PeerState(self, /, *args, **kwargs)
```

`Enum` class that represents the possible states of a [Peer](#peer) instance.

__Attributes__

- `STARTING (enum)`: connecting to signaling server.
- `ONLINE (enum)`: connected to signaling server but not paired to any peer.
- `LISTENING (enum)`: pairing and establishing a WebRTC connection with peer.
- `CONNECTING (enum)`: WebRTC peer connection and data channel are ready.
- `CONNECTED (enum)`: closing peer connection.
- `DISCONNECTING (enum)`: waiting for incoming connections.
- `CLOSING (enum)`: disconnecting from signaling server.
- `CLOSED (enum)`: disconnected from signaling server and not longer usable.

