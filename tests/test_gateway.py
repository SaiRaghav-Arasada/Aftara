import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from aiohttp import web
from aiohttp.test_utils import TestClient,TestServer
from accounts import Accounts
import gateway

class GatewayTests(unittest.IsolatedAsyncioTestCase):
 async def test_remote_browser_requires_matching_account_and_origin(self):
  with tempfile.TemporaryDirectory() as d,patch.object(gateway.app,'ROOT',Path(d)):
   accounts=Accounts(d)
   uid=accounts.register('one@example.com','long-test-password')
   uid2=accounts.register('two@example.com','long-test-password')
   one=accounts.create_session(uid);two=accounts.create_session(uid2);accounts.close()
   async def rfb(reader,writer):
    writer.write(b'RFB 003.008\n');await writer.drain()
    await reader.read();writer.close();await writer.wait_closed()
   tcp=await asyncio.start_server(rfb,'127.0.0.1',0)
   port=tcp.sockets[0].getsockname()[1]
   application=web.Application();application.router.add_get('/remote/{tail:.*}',gateway.remote)
   async with TestClient(TestServer(application)) as client:
    response=await client.get('/remote/vnc.html',allow_redirects=False)
    self.assertEqual(response.status,302)
    with patch('gateway.remote_desktop.get',side_effect=lambda x:{'port':port} if x==uid else None):
     response=await client.get('/remote/websockify',headers={'Cookie':'li_session='+one,'Origin':'https://wrong.example'})
     self.assertEqual(response.status,403)
     response=await client.get('/remote/websockify',headers={'Cookie':'li_session='+two,'Origin':gateway.ORIGIN})
     self.assertEqual(response.status,409)
     async with client.ws_connect('/remote/websockify',headers={'Cookie':'li_session='+one,'Origin':gateway.ORIGIN}) as ws:
      self.assertEqual((await ws.receive()).data,b'RFB 003.008\n')
   tcp.close();await tcp.wait_closed()
