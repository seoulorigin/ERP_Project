import asyncio
import websockets
import json
from flask import Flask, request
import threading

# Flask 앱 (내부 서비스 트리거용)
app = Flask(__name__)
connected_clients = {} # {employeeId: websocket}

async def ws_handler(websocket, path):
    # URL 파라미터 파싱: /ws?id={employeeId}
    try:
        query = path.split('?')
        if len(query) > 1:
            params = query[1].split('=')
            if params[0] == 'id':
                emp_id = int(params[1])
                connected_clients[emp_id] = websocket
                print(f"Client {emp_id} connected")
                await websocket.wait_closed()
    except Exception as e:
        print(f"Error: {e}")
    finally:
        # 연결 종료 처리 로직 필요
        pass

# Request Service가 호출하는 알림 트리거 API
@app.route('/notify', methods=['POST'])
def trigger_notification():
    data = request.json
    # 실제로는 requesterId를 조회해서 보내야 함. 여기선 1번 직원에게 보낸다고 가정.
    target_id = 1 
    
    if target_id in connected_clients:
        ws = connected_clients[target_id]
        msg = json.dumps(data)
        # 비동기 루프에 태스크 추가
        asyncio.run_coroutine_threadsafe(ws.send(msg), loop)
        
    return "Notification Sent", 200

# WebSocket 서버 실행
loop = asyncio.new_event_loop()

def start_ws():
    asyncio.set_event_loop(loop)
    start_server = websockets.serve(ws_handler, "0.0.0.0", 8085)
    loop.run_until_complete(start_server)
    loop.run_forever()

if __name__ == '__main__':
    t = threading.Thread(target=start_ws)
    t.start()
    app.run(port=5004, debug=True)