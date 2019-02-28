# hyperpeer-node
hyperpeer-node is a Node.js module for implementing the signaling server in applications based on Hyperpeer.
This module provides a single class called [`HyperpeerServer`](#HyperpeerServer) which manages the connection, 
pairing and WebRTC signals exchange of Hyperpeer peers.

# Example
```js
const HpServer = require('hyperpeer-node')

// Function used to validate and authorize peers 
const verifyPeer = function(type, peerId, peerKey) {
    const validTypes = new Set(['client', 'advisor', 'media-server'])
    const peerIds = new Map([['client01', 'key001'], ['advisor01', 'key002'])
    if (!validTypes.has(type)) return false
    if (!peerIds.has(peerId)) return false
    if (peerKey != peerIds.key(peerId)) return false
    return true
}

// Instantiate the Hyperpeer server by automatically creating an HTTP server
const hpServer = new HpServer({ port: 3000, verifyPeer: verifyPeer })

// And that's it
console.log((new Date()) + ' Hyperpeer Server is listening on port 3000')

// Hyperpeer instances are also WebSocket.Server instances so you can listen to its events like the 'connection' event
hpServer.on('connection', () => {
    const peers = hpServer.getPeers()
    console.log('New peer connection. Connected peers: ' + peers.map((peer) => peer.id))
}) 
 ```

# API Reference

<a name="HyperpeerServer"></a>

## HyperpeerServer ⇐ <code>WebSocket.Server</code>
**Kind**: global class  
**Extends**: <code>WebSocket.Server</code>  

* [HyperpeerServer](#HyperpeerServer) ⇐ <code>WebSocket.Server</code>
    * [new HyperpeerServer(options)](#new_HyperpeerServer_new)
    * _instance_
        * [.getPeers()](#HyperpeerServer+getPeers) ⇒ [<code>Array.&lt;peer&gt;</code>](#HyperpeerServer..peer)
    * _inner_
        * [~verifyPeer](#HyperpeerServer..verifyPeer) : <code>function</code>
        * [~peer](#HyperpeerServer..peer) : <code>Object</code>

<a name="new_HyperpeerServer_new"></a>

### new HyperpeerServer(options)
Creates an instance of HyperpeerServer which is a wrapper of the [WebSocket.Server](https://github.com/websockets/ws/blob/HEAD/doc/ws.md) class. HyperpeerServer instances manages the connection of peers, the pairing between peers, and relay messages between paired peers.


| Param | Type | Description |
| --- | --- | --- |
| options | <code>object</code> | Websocket server options (see [ ws API](https://github.com/websockets/ws/blob/HEAD/doc/ws.md)) |
| options.verifyPeer | [<code>verifyPeer</code>](#HyperpeerServer..verifyPeer) | A function that can be used to validate peers. If set, it replaces verifyClient attribute of WebSocket.Server |

<a name="HyperpeerServer+getPeers"></a>

### hyperpeerServer.getPeers() ⇒ [<code>Array.&lt;peer&gt;</code>](#HyperpeerServer..peer)
Returns the list of connected peers

**Kind**: instance method of [<code>HyperpeerServer</code>](#HyperpeerServer)  
<a name="HyperpeerServer..verifyPeer"></a>

### HyperpeerServer~verifyPeer : <code>function</code>
Funcition to verify the connection of a peer

**Kind**: inner typedef of [<code>HyperpeerServer</code>](#HyperpeerServer)  

| Param | Type | Description |
| --- | --- | --- |
| peerType | <code>string</code> | Can be used to verify the category of the peer |
| peerId | <code>string</code> | Unique identifier of the peer |
| peerKey | <code>string</code> | Token that can be used to authenticate and authorize the peer |

<a name="HyperpeerServer..peer"></a>

### HyperpeerServer~peer : <code>Object</code>
Element of the list of peers.

**Kind**: inner typedef of [<code>HyperpeerServer</code>](#HyperpeerServer)  
**Properties**

| Name | Type | Description |
| --- | --- | --- |
| id | <code>string</code> | id of the peer. |
| type | <code>string</code> | type of the peer. |
| busy | <code>boolean</code> | Indicates whether the peer is paired with another peer. |

