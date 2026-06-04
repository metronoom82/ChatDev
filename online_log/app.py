import logging
import requests
import os
import json
import threading
import time
from flask import Flask, send_from_directory, request, jsonify
from flask_sock import Sock
import argparse

app = Flask(__name__, static_folder='static')
sock = Sock(app)
app.logger.setLevel(logging.ERROR)
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)
messages = []
port = [8000]

# ── Bit Office agent state ───────────────────────────────────
office_agents = {}
office_clients = []

def send_msg(role, text):
    try:
        data = {"role": role, "text": text}
        response = requests.post(f"http://127.0.0.1:{port[-1]}/send_message", json=data)
    except:
        logging.info("flask app.py did not start for online log")


@app.route("/")
def index():
    return send_from_directory("static", "index.html")


@app.route("/chain_visualizer")
def chain_visualizer():
    return send_from_directory("static", "chain_visualizer.html")


@app.route("/replay")
def replay():
    return send_from_directory("static", "replay.html")


@app.route("/office")
def office():
    """Bit Office — live agent visualization"""
    return send_from_directory("static", "office.html")


@app.route("/get_messages")
def get_messages():
    return jsonify(messages)


@app.route("/get_agents")
def get_agents():
    """Return current Bit Office agent state"""
    return jsonify(list(office_agents.values()))


@app.route("/send_message", methods=["POST"])
def send_message():
    data = request.get_json()
    role = data.get("role")
    text = data.get("text")

    avatarUrl = find_avatar_url(role)

    message = {"role": role, "text": text, "avatarUrl": avatarUrl}
    messages.append(message)

    # Also update office agent state
    agent_id = role.lower().replace(" ", "_")
    if agent_id not in office_agents:
        office_agents[agent_id] = {
            "agentId": agent_id,
            "name": role,
            "color": get_color(agent_id),
            "status": "working",
            "lastAction": text[:100],
            "worldX": (hash(agent_id) % 300) - 150,
            "worldY": (hash(agent_id + "y") % 160) - 80,
        }
    else:
        office_agents[agent_id]["lastAction"] = text[:100]
        office_agents[agent_id]["status"] = "working"
        # Reset to idle after 5s
        def reset_status(aid=agent_id):
            time.sleep(5)
            if aid in office_agents:
                office_agents[aid]["status"] = "done"
        threading.Thread(target=reset_status, daemon=True).start()

    # Broadcast to WebSocket clients
    broadcast_agent_update(agent_id)

    return jsonify(message)


@sock.route('/ws/office')
def office_ws(ws):
    """WebSocket endpoint for Bit Office live updates"""
    office_clients.append(ws)
    try:
        # Send current state
        for agent_id, agent in office_agents.items():
            ws.send(json.dumps({"type": "agent.action", **agent}))
        # Keep alive
        while True:
            data = ws.receive(timeout=30)
            if data is None: break
    except:
        pass
    finally:
        if ws in office_clients:
            office_clients.remove(ws)


def broadcast_agent_update(agent_id):
    if agent_id not in office_agents:
        return
    msg = json.dumps({"type": "agent.action", **office_agents[agent_id]})
    dead = []
    for client in office_clients:
        try:
            client.send(msg)
        except:
            dead.append(client)
    for d in dead:
        if d in office_clients:
            office_clients.remove(d)


def find_avatar_url(role):
    role = role.replace(" ", "%20")
    avatar_filename = f"avatars/{role}.png"
    avatar_url = f"/static/{avatar_filename}"
    return avatar_url


def get_color(agent_id):
    colors = ["#4f46e5","#0f766e","#b45309","#be123c","#4338ca","#0369a1","#7c3aed","#059669"]
    idx = sum(ord(c) for c in agent_id if c.isalpha()) % len(colors)
    return colors[idx]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='argparse')
    parser.add_argument('--port', type=int, default=8000, help="port")
    args = parser.parse_args()
    port.append(args.port)
    print(f"Please visit http://127.0.0.1:{port[-1]}/ for the front-end display page. \nIn the event of a port conflict, please modify the port argument (e.g., python3 app.py --port 8012).")
    app.run(host='0.0.0.0', debug=False, port=port[-1])
