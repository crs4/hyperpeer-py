#!/bin/sh
intro="
# hyperpeer-py
\nhyperpeer-py is the python module for implementing media servers or backend peers in applications based on Hyperpeer.
This module provides a class called [Peer](#Peer) which manages both the connection 
with the signaling server and the peer-to-peer communication via WebRTC with remote peers. It also provides an __Enum__
class called [PeerState](#PeerState) that defines the possible states of a [Peer](#Peer) instance.
\n\n# Features\n\n
- Built on top of [**asyncio**](https://docs.python.org/3/library/asyncio.html?highlight=asyncio#module-asyncio), 
Python’s standard asynchronous I/O framework. \n
- Based on the popular modules [aiortc](https://aiortc.readthedocs.io/en/latest/). \n
and [websockets](https://websockets.readthedocs.io/en/stable/). 
\n\n# API Documentation\n\n
"

{ echo -e $intro & pydocmd simple hyperpeer.hyperpeer.Peer+ hyperpeer.hyperpeer.PeerState; } > README.md