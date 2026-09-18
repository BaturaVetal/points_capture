import json
import datetime
from aiohttp import web

# Стан гри
game_state = {
    "active": False,
    "locations": {str(i): {"color": "grey", "history": []} for i in range(1, 11)},
    "scores": {"blue": 0, "red": 0},
    "loc_scores": {str(i): {"blue": 0, "red": 0} for i in range(1, 11)}
}
clients = set()

async def broadcast_state():
    """Надсилає оновлений стан всім підключеним клієнтам"""
    msg = json.dumps({"type": "state", "data": game_state})
    for ws in clients:
        await ws.send_str(msg)

async def websocket_handler(request):
    ws = web.WebSocketResponse()
    await ws.prepare(request)
    clients.add(ws)
    
    # При підключенні відправляємо поточний стан
    await ws.send_str(json.dumps({"type": "state", "data": game_state}))

    async for msg in ws:
        if msg.type == web.WSMsgType.TEXT:
            data = json.loads(msg.data)
            action = data.get("action")
            
            if action == "start":
                game_state["active"] = True
                # Скидаємо гру до початкового стану
                game_state["locations"] = {str(i): {"color": "grey", "history": []} for i in range(1, 11)}
                game_state["scores"] = {"blue": 0, "red": 0}
                game_state["loc_scores"] = {str(i): {"blue": 0, "red": 0} for i in range(1, 11)}
                await broadcast_state()
                
            elif action == "end":
                game_state["active"] = False
                
                # Формуємо CSV згідно з вимогами
                csv_lines = ["Локація,Історія захоплень (Час - Команда)"]
                for i in range(1, 11):
                    hist = game_state["locations"][str(i)]["history"]
                    hist_str = "; ".join([f"{h['time']} - {h['team']}" for h in hist])
                    csv_lines.append(f"Локація {i},{hist_str}")
                
                csv_lines.append("\nЛокація,Бали Синіх,Бали Червоних")
                for i in range(1, 11):
                    ls = game_state["loc_scores"][str(i)]
                    csv_lines.append(f"Локація {i},{ls['blue']},{ls['red']}")
                    
                csv_lines.append(f"\nЗАГАЛЬНА КІЛЬКІСТЬ БАЛІВ,{game_state['scores']['blue']},{game_state['scores']['red']}")
                csv_data = "\n".join(csv_lines)
                
                # Відправляємо результати всім
                for client in clients:
                    await client.send_str(json.dumps({"type": "end", "csv": csv_data}))
                
                # Робимо локації сірими
                for i in range(1, 11):
                    game_state["locations"][str(i)]["color"] = "grey"
                await broadcast_state()
                
            elif action == "capture":
                if not game_state["active"]:
                    continue
                    
                loc_id = str(data["loc_id"])
                new_team = data["team"] # "blue" або "red"
                current_color = game_state["locations"][loc_id]["color"]
                
                if current_color == new_team:
                    continue
                    
                # 1 бал за сіру, 2 бали за перезахоплення
                points = 1 if current_color == "grey" else 2
                game_state["scores"][new_team] += points
                game_state["loc_scores"][loc_id][new_team] += points
                game_state["locations"][loc_id]["color"] = new_team
                
                now = datetime.datetime.now().strftime("%H:%M:%S")
                game_state["locations"][loc_id]["history"].append({
                    "team": "Сині" if new_team == "blue" else "Червоні",
                    "time": now
                })
                
                await broadcast_state()
                
    clients.remove(ws)
    return ws

async def index(request):
    return web.FileResponse('index.html')

app = web.Application()
app.add_routes([web.get('/', index), web.get('/ws', websocket_handler)])

if __name__ == '__main__':
    # Запуск сервера
    print("Сервер запущено на http://localhost:8080")
    web.run_app(app, host='0.0.0.0', port=8080)