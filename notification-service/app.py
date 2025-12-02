import asyncio
import websockets
import json
from flask import Flask, request
import threading

# Flask 앱 (내부 서비스 트리거용)
app = Flask(__name__)
connected_clients = {} # {employeeId: websocket}

# 전역 이벤트 루프 생성 (Flask 라우트에서 접근하기 위함)
loop = asyncio.new_event_loop()

async def ws_handler(websocket):
    # path 인자 제거 (최신 websockets 버전 호환)
    try:
        # URL 파라미터 파싱 로직 (수동 처리)
        # path 속성은 websocket.request.path 등을 통해 접근 가능하지만,
        # 최신 버전에서는 핸들러 시그니처가 변경되었습니다.
        # 간단하게 구현하기 위해 현재는 모든 접속을 허용하고 메시지 대기
        
        # 실제 구현 시에는 path나 header를 통해 ID를 식별해야 함
        # 여기서는 테스트 편의상 1번 ID로 고정하거나 로직을 단순화합니다.
        
        # 예시: 접속하자마자 ID를 보내게 하거나, URL 쿼리를 파싱
        # 여기서는 간단히 path 파싱을 시도
        path = websocket.request.path
        query = path.split('?')
        if len(query) > 1:
            params = query[1].split('=')
            if params[0] == 'id':
                emp_id = int(params[1])
                connected_clients[emp_id] = websocket
                print(f"Client {emp_id} connected")
                await websocket.wait_closed()
        else:
             # ID가 없으면 그냥 닫기 (테스트 시 주의)
             await websocket.wait_closed()
             
    except Exception as e:
        print(f"Connection Error: {e}")
    finally:
        # 연결 종료 시 처리 (필요하면 추가)
        pass

@app.route('/notify', methods=['POST'])
def trigger_notification():
    data = request.json
    # 테스트를 위해 Requester ID를 1로 가정
    target_id = 1 
    
    if target_id in connected_clients:
        ws = connected_clients[target_id]
        msg = json.dumps(data)
        
        # 메인 스레드(Flask)에서 별도 스레드(WebSocket 루프)로 작업 전달
        asyncio.run_coroutine_threadsafe(ws.send(msg), loop)
        return "Notification Sent", 200
        
    return "Target not connected", 200

# WebSocket 서버 시작 로직 (수정됨)
def start_ws():
    asyncio.set_event_loop(loop)
    
    async def run_server():
        # 비동기 컨텍스트 매니저 사용 (최신 방식)
        async with websockets.serve(ws_handler, "0.0.0.0", 8085):
            print("WebSocket Server started on port 8085")
            await asyncio.Future()  # 영원히 대기 (서버 유지)

    # 루프 실행
    loop.run_until_complete(run_server())

if __name__ == '__main__':
    # 데몬 스레드로 실행하여 메인 프로세스 종료 시 함께 종료되도록 설정
    t = threading.Thread(target=start_ws, daemon=True)
    t.start()
    
    # Flask 실행
    app.run(port=5004, debug=True, use_reloader=False) 
    # use_reloader=False: 스레드 중복 실행 방지