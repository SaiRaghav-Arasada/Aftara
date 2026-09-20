"""Authenticated noVNC gateway and application proxy, behind HTTPS nginx."""
import asyncio
import os
import threading
from pathlib import Path
from urllib.parse import urlsplit
from aiohttp import web, ClientSession, WSMsgType, ClientTimeout
import app
from accounts import Accounts
import remote_desktop
from daily_reports import Scheduler
from http.server import ThreadingHTTPServer

ORIGIN=os.environ.get('LINKEDINAPPLY_PUBLIC_ORIGIN','http://127.0.0.1:8505')
ASSETS=Path('/usr/share/novnc')

def authenticated(request):
    accounts=Accounts(app.ROOT)
    try:return accounts.session(request.cookies.get('li_session',''))
    finally:accounts.close()

@web.middleware
async def host_guard(request,handler):
    if request.host not in (urlsplit(ORIGIN).netloc,'127.0.0.1:8080'):
        raise web.HTTPForbidden(text='Invalid host')
    return await handler(request)

async def remote(request):
    user=authenticated(request)
    if not user:raise web.HTTPFound('/login')
    if request.path=='/remote/websockify':
        if request.headers.get('Origin')!=ORIGIN:raise web.HTTPForbidden()
        desktop=remote_desktop.get(user['id'])
        if not desktop:raise web.HTTPConflict(text='Open LinkedIn from Find & prepare first.')
        reader,writer=await asyncio.open_connection('127.0.0.1',desktop['port'])
        ws=web.WebSocketResponse(protocols=('binary',),heartbeat=20,max_msg_size=2**20)
        await ws.prepare(request)
        async def upstream():
            while True:
                data=await reader.read(65536)
                if not data:break
                await ws.send_bytes(data)
        async def downstream():
            async for msg in ws:
                if msg.type==WSMsgType.BINARY:
                    writer.write(msg.data);await writer.drain()
                elif msg.type in (WSMsgType.ERROR,WSMsgType.CLOSE):break
        async def check_session():
            while authenticated(request):await asyncio.sleep(10)
        tasks=[asyncio.create_task(f()) for f in (upstream,downstream,check_session)]
        try:await asyncio.wait(tasks,return_when=asyncio.FIRST_COMPLETED)
        finally:
            for task in tasks:task.cancel()
            await asyncio.gather(*tasks,return_exceptions=True)
            writer.close();await writer.wait_closed();await ws.close()
        return ws
    path=(ASSETS/request.match_info['tail']).resolve()
    if not path.is_relative_to(ASSETS) or not path.is_file():raise web.HTTPNotFound()
    return web.FileResponse(path,headers={'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'})

async def proxy(request):
    # The private upstream remains loopback-only; forwarded identity headers are ignored.
    headers={k:v for k,v in request.headers.items() if k.lower() not in ('host','connection','transfer-encoding','content-length','upgrade')}
    headers['Host']='127.0.0.1:8501'
    async with request.app['client'].request(request.method,'http://127.0.0.1:8501'+str(request.rel_url),headers=headers,data=await request.read(),allow_redirects=False) as response:
        result=web.Response(status=response.status,body=await response.read())
        for k,v in response.headers.items():
            if k.lower() not in ('connection','transfer-encoding','content-encoding','content-length'):
                result.headers.add(k,v)
        return result

async def lifecycle(application):
    application['client']=ClientSession(timeout=ClientTimeout(total=180))
    yield
    await application['client'].close()
    remote_desktop.stop_all()

if __name__=='__main__':
    server=ThreadingHTTPServer(('127.0.0.1',8501),app.Handler)
    threading.Thread(target=server.serve_forever,daemon=True).start()
    Scheduler(app.ROOT).start()
    application=web.Application(client_max_size=21_000_000,middlewares=[host_guard])
    application.cleanup_ctx.append(lifecycle)
    application.router.add_route('GET','/remote/{tail:.*}',remote)
    application.router.add_route('*','/{tail:.*}',proxy)
    web.run_app(application,host='127.0.0.1',port=8080,access_log=None)
