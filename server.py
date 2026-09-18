import json
import datetime
import os
from aiohttp import web

# ТУТ МОЖНА ЗМІНИТИ НАЗВИ ЛОКАЦІЙ
LOC_NAMES = {
    "1": "Вінтерфелл",
    "2": "Королівська Гавань",
    "3": "Драконів Камінь",
    "4": "Ріверран",
    "5": "Орлине Гніздо",
    "6": "Пайк",
    "7": "Скеля Кастерлі",
    "8": "Хайгарден",
    "9": "Штормова Межа",
    "10": "Дорн"
}

def get_initial_locations():
    return {str(i): {"name": LOC_NAMES[str(i)], "color": "grey", "history": []} for i in range(1, 11)}

game_state = {
    "active": False,
    "locations": get_initial_locations(),
    "scores": {"blue": 0, "red": 0},
    "loc_scores": {str(i): {"blue": 0, "red": 0} for i in range(1, 11)}
}
clients = set()

async def broadcast_state():
    msg = json.dumps({"type": "state", "data": game_state})
    for ws in clients:
        await ws.send_str(msg)

async def websocket_handler(request):
    ws = web.WebSocketResponse()
    await ws.prepare(request)
    clients.add(ws)
    
    await ws.send_str(json.dumps({"type": "state", "data": game_state}))

    async for msg in ws:
        if msg.type == web.WSMsgType.TEXT:
            data = json.loads(msg.data)
            action = data.get("action")
            
            if action == "ping":
                # Просто розсилаємо стан, щоб підтримати активність
                await ws.send_str(json.dumps({"type": "pong"}))
                
            elif action == "start":
                game_state["active"] = True
                game_state["locations"] = get_initial_locations()
                game_state["scores"] = {"blue": 0, "red": 0}
                game_state["loc_scores"] = {str(i): {"blue": 0, "red": 0} for i in range(1, 11)}
                await broadcast_state()
                
            elif action == "end":
                game_state["active"] = False
                
                # Формуємо CSV з реальними назвами
                csv_lines = ["Локація,Історія захоплень (Час - Команда)"]
                for i in range(1, 11):
                    loc_data = game_state["locations"][str(i)]
                    hist_str = "; ".join([f"{h['time']} - {h['team']}" for h in loc_data['history']])
                    csv_lines.append(f"{loc_data['name']},{hist_str}")
                
                csv_lines.append("\nЛокація,Бали Синіх,Бали Червоних")
                for i in range(1, 11):
                    loc_name = game_state["locations"][str(i)]["name"]
                    ls = game_state["loc_scores"][str(i)]
                    csv_lines.append(f"{loc_name},{ls['blue']},{ls['red']}")
                    
                csv_lines.append(f"\nЗАГАЛЬНА КІЛЬКІСТЬ БАЛІВ,{game_state['scores']['blue']},{game_state['scores']['red']}")
                csv_data = "\n".join(csv_lines)
                
                # Відправляємо результати
                for client in clients:
                    await client.send_str(json.dumps({"type": "end", "csv": csv_data}))
                
                for i in range(1, 11):
                    game_state["locations"][str(i)]["color"] = "grey"
                await broadcast_state()
                
            elif action == "capture":
                if not game_state["active"]:
                    continue
                    
                loc_id = str(data["loc_id"])
                new_team = data["team"]
                current_color = game_state["locations"][loc_id]["color"]
                
                if current_color == new_team:
                    continue
                    
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
    port = int(os.environ.get("PORT", 8080))
    print(f"Сервер запускається на порту {port}")
    web.run_app(app, host='0.0.0.0', port=port)
