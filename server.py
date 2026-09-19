import json
import datetime
import os
import time
from aiohttp import web

LOC_NAMES = {
    "1": "Брама Тіней",
    "2": "Королівський Бенкет Кухарів",
    "3": "Сховище таємниць",
    "4": "Скарб Трясовини та Вод",
    "5": "Остання Вода Чорної Ріки",
    "6": "Вежа Високих Прагнень",
    "7": "Ліс Сліпих Інстинктів",
    "8": "Тераса Червоних Пут",
    "9": "Поля Турнірів",
    "10": "Таємниця Темряви"
}

def get_initial_locations():
    return {
        str(i): {
            "name": LOC_NAMES[str(i)], 
            "color": "grey", 
            "history": [], 
            "locked_until": 0  # Час, до якого діє башта
        } for i in range(1, 11)
    }

game_state = {
    "active": False,
    "locations": get_initial_locations(),
    "scores": {"blue": 0, "red": 0},
    "loc_scores": {str(i): {"blue": 0, "red": 0} for i in range(1, 11)}
}
clients = set()

async def broadcast_state():
    msg = json.dumps({
        "type": "state", 
        "data": game_state,
        "server_time": time.time()  # Передаємо час сервера для точних таймерів
    })
    for ws in clients:
        try:
            await ws.send_str(msg)
        except:
            pass

async def websocket_handler(request):
    ws = web.WebSocketResponse()
    await ws.prepare(request)
    clients.add(ws)
    
    await ws.send_str(json.dumps({
        "type": "state", 
        "data": game_state,
        "server_time": time.time()
    }))

    async for msg in ws:
        if msg.type == web.WSMsgType.TEXT:
            data = json.loads(msg.data)
            action = data.get("action")
            
            if action == "ping":
                await ws.send_str(json.dumps({"type": "pong"}))
                
            elif action == "start":
                game_state["active"] = True
                game_state["locations"] = get_initial_locations()
                game_state["scores"] = {"blue": 0, "red": 0}
                game_state["loc_scores"] = {str(i): {"blue": 0, "red": 0} for i in range(1, 11)}
                await broadcast_state()
                
            elif action == "end":
                game_state["active"] = False
                
                # Формуємо CSV структуру для файлу
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
                
                # Відправляємо результати і фінальний стан для красивої таблиці
                final_msg = json.dumps({
                    "type": "end", 
                    "csv": csv_data, 
                    "final_state": game_state
                })
                for client in clients:
                    try:
                        await client.send_str(final_msg)
                    except:
                        pass
                
                # Скидаємо кольори
                for i in range(1, 11):
                    game_state["locations"][str(i)]["color"] = "grey"
                    game_state["locations"][str(i)]["locked_until"] = 0
                await broadcast_state()
                
            elif action in ["capture", "tower_capture"]:
                if not game_state["active"]:
                    continue
                    
                loc_id = str(data["loc_id"])
                new_team = data["team"]
                loc_data = game_state["locations"][loc_id]
                current_color = loc_data["color"]
                
                # Перевірка, чи не заблокована локація баштою
                if loc_data["locked_until"] > time.time():
                    continue
                
                team_name = "Сині" if new_team == "blue" else "Червоні"
                is_tower = (action == "tower_capture")
                
                # Якщо ставлять башту, вона діє 5 хвилин (300 секунд)
                if is_tower:
                    loc_data["locked_until"] = time.time() + 300
                    team_name = f"🗼 {team_name} (Башта)"

                # Якщо колір змінився, даємо бали
                if current_color != new_team:
                    points = 1 if current_color == "grey" else 2
                    game_state["scores"][new_team] += points
                    game_state["loc_scores"][loc_id][new_team] += points
                    loc_data["color"] = new_team
                    
                    now = datetime.datetime.now().strftime("%H:%M:%S")
                    loc_data["history"].append({
                        "team": team_name,
                        "time": now
                    })
                elif is_tower:
                    # Якщо колір той самий, але купили башту для захисту, просто записуємо історію без балів
                    now = datetime.datetime.now().strftime("%H:%M:%S")
                    loc_data["history"].append({
                        "team": team_name + " - Захист",
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
