import unittest
import asyncio
from hyperpeer import Peer, PeerState
import subprocess
import sys
import numpy
import time

import logging

logging.basicConfig(level=logging.INFO)

def async_test(f):
    def wrapper(*args, **kwargs):
        coro = asyncio.coroutine(f)
        future = coro(*args, **kwargs)
        loop = asyncio.get_event_loop()
        loop.set_debug(True)
        loop.run_until_complete(future)
    return wrapper

class TestPeer(unittest.TestCase):
    @classmethod
    def setUpClass(self):
        try:
            self.server = subprocess.Popen(
            ['node', './test/testServer.js'], stderr=subprocess.PIPE, stdout=subprocess.PIPE)
        except:
            print('Test server error!')
            raise
        try:
            print(self.server.communicate(timeout=1))
        except subprocess.TimeoutExpired:
            print('nothing from server')
        # 156.148.132.107

    @classmethod
    def tearDownClass(self):
        try:
            print('Getting messages from server...')
            outs, errs = self.server.communicate(timeout=1)
            print('Outs: ' + outs.decode('utf8') + '. Errs: ' + errs.decode('utf8'))
        except subprocess.TimeoutExpired:
            self.server.kill()
            print('Final messages from server...')
            outs, errs = self.server.communicate(timeout=1)
            print('Outs: ' + outs.decode('utf8') + '. Errs: ' + errs.decode('utf8'))
        except Exception as err:
            print(err)

    def setUp(self):
        self.peer = Peer('ws://localhost:8080',
                         peer_type='media-server', id='server1')
        self.peer2 = Peer('ws://localhost:8080', peer_type='test', id='server2')

    def tearDown(self):
        async def clean():
            await self.peer.close()
            await self.peer2.close()
        asyncio.get_event_loop().run_until_complete(clean())
        #self.peer.close()

    @unittest.skip("demonstrating skipping")
    @async_test
    async def test_server_connection(self):
        self.assertEqual(self.peer.readyState, PeerState.STARTING)
        await self.peer.open()
        self.assertEqual(self.peer.readyState, PeerState.ONLINE)
        await self.peer.close()
        self.assertEqual(self.peer.readyState, PeerState.CLOSED)

    @unittest.skip("demonstrating skipping")
    @async_test
    async def test_peers(self):
        await self.peer.open()
        peers = await self.peer.get_peers()
        self.assertIsInstance(peers, list)

    @unittest.skip("demonstrating skipping")
    @async_test
    async def test_connect(self):
        await self.peer.open()
        await self.peer2.open()
        async def peer2_actions():
            print('listening...')
            try: 
                await self.peer2.listen_connections()
            except asyncio.CancelledError:
                print('canceled!')
                self.peer2.disconnect()
                raise
            await asyncio.sleep(0.5)
            self.assertEqual(self.peer2.readyState, PeerState.CONNECTING)
            self.assertEqual(self.peer.readyState, PeerState.CONNECTING)
            print('receiving call...')
            await self.peer2.accept_connection()
            print('negotiating...')

        peer2_task = asyncio.create_task(peer2_actions())
        print('calling...')
        peer1_task = asyncio.create_task(self.peer.connect_to('server2'))
        await peer1_task
        print('answering...')
        await asyncio.wait_for(peer2_task, 10)
        print('connected!')
        self.assertEqual(self.peer2.readyState, PeerState.CONNECTED)
        self.assertEqual(self.peer.readyState, PeerState.CONNECTED)
        await self.peer.disconnect()
        print(self.peer.readyState)
        self.assertEqual(self.peer.readyState, PeerState.ONLINE)
        await self.peer2.disconnect()

    @unittest.skip("demonstrating skipping")
    @async_test
    async def test_datachannel_poll(self):
        await self.peer.open()
        await self.peer2.open()

        async def peer2_actions():
            await self.peer2.listen_connections()
            await self.peer2.accept_connection()

        peer2_task = asyncio.create_task(peer2_actions())
        print('calling...')
        peer1_task = asyncio.create_task(self.peer.connect_to('server2'))
        try:
            await peer1_task
            print('answering...')
            await asyncio.wait_for(peer2_task, 10)
            print('connected!')
            await self.peer.send('ciao')
            data = await self.peer2.recv()
            self.assertEqual(data, 'ciao')
            await self.peer2.send({'foo': 'bar'})
            data = await self.peer.recv()
            self.assertIsInstance(data, dict)
            self.assertEqual(data['foo'], 'bar')
        except Exception as err:
            print(err)
            raise
        finally:
            await self.peer.disconnect()
            await self.peer2.disconnect()
            await self.peer.close()
            await self.peer2.close()

    @unittest.skip("demonstrating skipping")
    @async_test
    async def test_datachannel_stream(self):
        await self.peer.open()
        await self.peer2.open()

        async def peer2_actions():
            await self.peer2.listen_connections()
            await self.peer2.accept_connection()

        peer2_task = asyncio.create_task(peer2_actions())
        print('calling...')
        peer1_task = asyncio.create_task(self.peer.connect_to('server2'))
        try:
            await peer1_task
            print('answering...')
            await asyncio.wait_for(peer2_task, 10)
            print('connected!')

            async def sender():
                sent = 0
                while sent < 10:
                    await self.peer.send({'inc': 1})
                    sent += 1
                    await asyncio.sleep(0.01)

            self.count = 0
            def on_data(data):
                self.count += data['inc']

            self.count2 = 0
            async def on_data_async(data):
                self.count2 += data['inc']

            self.peer2.add_data_handler(on_data)
            self.peer2.add_data_handler(on_data_async)
            await asyncio.wait_for(sender(), timeout=1)
            await asyncio.sleep(0.2)
            self.assertEqual(self.count, 10)
            self.assertEqual(self.count2, 10)
            print('Data test OK')
        except Exception as err:
            print(err)
            raise
        finally:
            await self.peer.disconnect()
            await self.peer2.disconnect()
            await self.peer.close()
            await self.peer2.close()

    # @unittest.skip("demonstrating skipping")
    @async_test
    async def test_video_and_data(self):
        
        def video_frame_generator():
            print('generator started')
            frames = 0
            while True:
                frame = numpy.random.rand(720, 1280, 3)
                frame = numpy.uint8(frame * 100)
                frames += 1
                #print('generating frame: ' + str(frames))
                yield frame

        self.received_frames = []
        def frame_consumer(frame):
            self.received_frames.append(frame)
            #print('received frame: ' + str(len(self.received_frames)))
            

        self.peer2 = Peer('ws://localhost:8080', peer_type='test',
                          id='server2', frame_generator=video_frame_generator)
        self.peer = Peer('ws://localhost:8080',
                         peer_type='media-server', id='server1', frame_consumer=frame_consumer)

        await self.peer.open()
        await self.peer2.open()

        self.sent = 0
        async def sender():
            frames = 0
            while frames < 10:
                frames = len(self.received_frames)
                await self.peer.send({'credit': 1})
                self.sent += 1
                await asyncio.sleep(0.01)

        self.credits = 0
        def on_data(data):
            self.credits += data['credit']

        self.peer2.add_data_handler(on_data)

        async def peer1_actions():
            await self.peer.listen_connections()
            await self.peer.accept_connection()
        print('connecting...')
        peer1_task = asyncio.create_task(peer1_actions())
        peer2_task = asyncio.create_task(self.peer2.connect_to('server1'))
        await asyncio.gather(peer1_task, peer2_task)
        print('connected!')
        sender_task = asyncio.create_task(sender())
        async def wait_frames():
            while len(self.received_frames) < 15:
                await asyncio.sleep(0.1)
        
        try:
            await asyncio.wait_for(wait_frames(), timeout=5.0)
            await sender_task
            self.assertTrue(len(self.received_frames) >= 15)
            self.assertIsInstance(self.received_frames[0], numpy.ndarray)
            self.assertEqual(self.received_frames[0].shape, (720, 1280, 3))
            self.assertTrue(self.credits == self.sent)
        except asyncio.TimeoutError:
            print('timeout!')
            raise
        finally:
            await self.peer.disconnect()
            await self.peer2.disconnect()
            await self.peer.close()
            await self.peer2.close()

    # @unittest.skip("demonstrating skipping")
    @async_test
    async def test_frame_rate(self):
        
        frame = numpy.random.rand(720, 1280, 3)
        frame = numpy.uint8(frame * 100)
        self.last_time = time.time()
        def video_frame_coroutine():
            while True:
                yield frame

        self.received_frames = []
        self.start_time = 0
        def frame_consumer(frame):
            if len(self.received_frames) == 0:
                print('timer start')
                self.start_time = time.time()
            self.received_frames.append(frame)
            if len(self.received_frames) == 100:
                self.stop_time = time.time()
                print('timer stop')
            #print('received frame: ' + str(len(self.received_frames)))
            

        self.peer2 = Peer('ws://localhost:8080', peer_type='test',
                          id='server2', frame_generator=video_frame_coroutine, frame_rate=10)
        self.peer = Peer('ws://localhost:8080',
                         peer_type='media-server', id='server1', frame_consumer=frame_consumer)

        await self.peer.open()
        await self.peer2.open()


        async def peer2_actions():
            await self.peer2.listen_connections()
            await self.peer2.accept_connection()
        print('connecting...')
        peer2_task = asyncio.create_task(peer2_actions())
        peer1_task = asyncio.create_task(self.peer.connect_to('server2'))
        await asyncio.gather(peer1_task, peer2_task)
        print('connected!')
        async def wait_frames():
            while len(self.received_frames) < 100:
                await asyncio.sleep(0.1)
        
        try:
            await asyncio.wait_for(wait_frames(), timeout=15.0)
            self.assertTrue(len(self.received_frames) >= 100)
            self.assertIsInstance(self.received_frames[0], numpy.ndarray)
            self.assertEqual(self.received_frames[0].shape, (720, 1280, 3))
            time_100_frames = self.stop_time - self.start_time
            print(f'Time for 100 frames: {time_100_frames}')
            self.assertTrue(time_100_frames > 9 and time_100_frames < 11)
        except asyncio.TimeoutError:
            print('timeout!')
            raise
        finally:
            await self.peer.disconnect()
            await self.peer2.disconnect()
            await self.peer.close()
            await self.peer2.close()

    # @unittest.skip("demonstrating skipping")
    @async_test
    async def test_video_player(self):

        self.received_frames = []

        def frame_consumer(frame):
            self.received_frames.append(frame)
            #print('received frame: ' + str(len(self.received_frames)))

        self.peer2 = Peer('ws://localhost:8080',
                          peer_type='media-player', id='player1', media_source='./test/SampleVideo_1280x720_1mb.mp4', media_source_format='mp4')
        self.peer = Peer('ws://localhost:8080',
                         peer_type='media-client', id='client1', frame_consumer=frame_consumer)

        await self.peer.open()
        await self.peer2.open()

        async def peer2_actions():
            await self.peer2.listen_connections()
            await self.peer2.accept_connection()
        print('connecting...')
        peer2_task = asyncio.create_task(peer2_actions())
        peer1_task = asyncio.create_task(self.peer.connect_to('player1'))
        await asyncio.gather(peer1_task, peer2_task)
        print('connected!')

        async def wait_frames():
            while len(self.received_frames) < 130:
                await asyncio.sleep(0.1)
        try:
            print('Waiting video to complete...')
            # await asyncio.wait_for(wait_frames(), timeout=7.0)
            await self.peer2.disconnection_event.wait()
            self.assertTrue(len(self.received_frames) >= 130)
        except asyncio.TimeoutError:
            print('timeout!')
            print('Frames:', len(self.received_frames))
        finally:
            await self.peer.disconnect()
            await self.peer2.disconnect()
            await self.peer.close()
            await self.peer2.close()
        
        
if __name__ == '__main__':
    unittest.main()
