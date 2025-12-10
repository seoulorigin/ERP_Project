import asyncio
import websockets
import json
import threading
import sys
import traceback
from flask import Flask, request, jsonify
from flask_restx import Api, Resource, fields
from urllib.parse import urlparse, parse_qs

app = Flask(__name__)
api = Api(app)
ns = api.namespace('notify', description='Notification operations')

connected_clients = {}
ws_loop = None

notification_model = api.model('Notification', {
    'targetId': fields.String(required=True, description='Target Employee ID'),
    'payload': fields.Raw(required=True, description='Payload')
})

# --- WebSocket Server ---
async def handler(websocket):
    # [수정됨] 최신 버전 호환성 수정 (websocket.path -> websocket.request.path)
    try:
        path = websocket.request.path
    except AttributeError:
        # 혹시 모를 구버전 호환성을 위해 예외 처리
        path = getattr(websocket, 'path', '/')

    print(f"\n[WS Debug] Connection attempt from: {path}")
    
    try:
        parsed_url = urlparse(path)
        params = parse_qs(parsed_url.query)
        
        # ID 추출
        raw_id = params.get('id', [None])[0]
        
        if not raw_id:
            print(f"[WS Debug] Rejected: No 'id' parameter found")
            await websocket.close()
            return

        user_id = str(raw_id)
        
        connected_clients[user_id] = websocket
        print(f"[WS] User connected: '{user_id}'")
        print(f"[WS] Current Clients: {list(connected_clients.keys())}")
        
        # 연결 유지 루프
        async for message in websocket:
            pass 
            
    except Exception as e:
        print(f"[WS Error] Internal Server Error: {e}")
        traceback.print_exc()
        
    finally:
        if 'user_id' in locals() and user_id in connected_clients:
            del connected_clients[user_id]
        print(f"[WS] Connection closed/cleaned up")

async def start_server():
    global ws_loop
    ws_loop = asyncio.get_running_loop()
    
    PORT = 8081
    print(f"Notification WebSocket Server running on port {PORT}...")
    # 0.0.0.0으로 열어서 외부 접속 허용
    async with websockets.serve(handler, "0.0.0.0", PORT):
        await asyncio.Future()

def run_ws_in_thread():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(start_server())

# --- HTTP API ---
@ns.route('')
class NotificationResource(Resource):
    @ns.expect(notification_model)
    def post(self):
        data = request.json
        target_id = str(data.get('targetId'))
        payload = data.get('payload')

        print(f"\n[HTTP] Sending to User: '{target_id}'")
        
        if target_id in connected_clients:
            ws = connected_clients[target_id]
            message = json.dumps(payload)
            
            if ws_loop:
                asyncio.run_coroutine_threadsafe(ws.send(message), ws_loop)
                return {"status": "sent", "targetId": target_id}, 200
        
        # 디버깅용 로그: 현재 누구누구 접속해 있는지 출력
        print(f"[HTTP] User '{target_id}' not connected. (Current: {list(connected_clients.keys())})")
        return {"status": "skipped", "reason": "User not connected"}, 200

if __name__ == '__main__':
    t = threading.Thread(target=run_ws_in_thread)
    t.daemon = True
    t.start()
    
    app.run(port=5004, debug=True, use_reloader=False)