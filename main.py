#run commands in pycharm terminal to install flask and socketio
#pip install Flask
#pip install flask-socketio

from socket import SocketIO

from flask import Flask, render_template, request, session, redirect, url_for
from flask_socketio import join_room, leave_room, send, SocketIO
import random
from string import ascii_uppercase

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
socketio = SocketIO(app)

rooms = {}


def generate_unique_code(Length):
    """
    -Returns a random string of uppercase letters and digits
    -No Duplicate codes
    """
    while True:
        code = "".join(random.choice(ascii_uppercase) for _ in range(Length))
        if code not in rooms:
            return code


@app.route('/', methods=['POST', 'GET'])
def home():
    """
    -Renders the home page, and handles room creation/joining
    """
    session.clear()
    if request.method == 'POST':
        name = request.form.get('name')
        code = request.form.get('code')
        join = request.form.get('join', False)
        create = request.form.get('create', False)
        capacity = request.form.get('capacity', '10')  # Get capacity from form

        if not name:
            return render_template('home.html', error="Please enter a name.", code=code, name=name)
        if join != False and not code:
            return render_template('home.html', error="Please enter a room code.", code=code, name=name)

        room = code
        if create != False:
            room = generate_unique_code(4)
            try:
                max_capacity = int(capacity)
                if max_capacity < 1:
                    max_capacity = 10
            except:
                max_capacity = 10

            rooms[room] = {
                "members": 0,
                "messages": [],
                "capacity": max_capacity,
                "host": name
            }
        elif code not in rooms:
            return render_template('home.html', error="Room does not exist.", code=code, name=name)
        else:
            # Check if room is full
            if rooms[code]["members"] >= rooms[code]["capacity"]:
                return render_template('home.html', error="Room is full.", code=code, name=name)

        # semi-permanent way to store info about a user
        session["room"] = room
        session["name"] = name
        return redirect(url_for("room"))

    return render_template('home.html')


@app.route("/room")
def room():
    """
    -Renders the chat room page
    -Ensures user belongs to a valid room
    -Distinction between host screen and member screen
    """
    room = session.get("room")
    name = session.get("name")
    if room is None or name is None or room not in rooms:
        return redirect(url_for("home"))

    is_host = (rooms[room].get("host") == name)
    return render_template("room.html",
                           room=room,
                           name=name,
                           messages=rooms[room]["messages"],
                           capacity=rooms[room]["capacity"],
                           current_members=rooms[room]["members"],
                           is_host=is_host)


@socketio.on('join')
def handle_join(message):
    """
    -Handles a user joining a room
    -Updates member count
    -Notifies room members
    """
    room = session.get("room")
    name = session.get("name")
    if not room or not name:
        return
    if room not in rooms:
        leave_room(room)
        return

    rooms[room]['members'] += 1
    join_room(room)
    send({
        'name': name,
        'message': 'has entered the room'}, to=room)
    socketio.emit('member_update', {
        'members': rooms[room]['members'],
        'capacity': rooms[room]['capacity'],
    }, room=room)


@socketio.on('disconnect')
def disconnect():
    """
    -Handles a user disconnecting
    -Updates room count
    -Notifies room members
    -Deletes room if empty
    """
    room = session.get("room")
    name = session.get("name")
    leave_room(room)

    # member count(if 0, room is deleted)
    if room in rooms:
        rooms[room]["members"] -= 1
        new_members = rooms[room]["members"]

        send({
            'name': name,
            'message': 'has left the room'}, to=room)

        if new_members > 0:
            socketio.emit('member_update', {
                'members': new_members,
                'capacity': rooms[room]["capacity"],
            }, room=room)

        if new_members <= 0:
            del rooms[room]

@socketio.on('message')
def message(data):
    """
    -Handles messages sent by clients
    -Displays message in the chat
    """
    room = session.get("room")
    if room not in rooms:
        return

    content = {
        'name': session.get('name'),
        'message': data['data'],

    }
    send(content, to=room)
    rooms[room]['messages'].append(content)
    print(f"{session.get('name')} said: {data['data']}")


@socketio.on('update_capacity')
def update_capacity(data):
    """
    -Handles Host updating capacity
    -Notifies room members
    """
    room = session.get("room")
    name = session.get("name")

    if room not in rooms or rooms[room].get("host") != name:
        return  # Only host can update capacity

    try:
        new_capacity = int(data['capacity'])
        if new_capacity >= rooms[room]["members"]:  # Can't set lower than current members
            rooms[room]["capacity"] = new_capacity
            send({
                'name': 'System',
                'message': f'Room capacity updated to {new_capacity}'
            }, to=room)
    except:
        pass


if __name__ == '__main__':
    socketio.run(app, debug=True, allow_unsafe_werkzeug=True)