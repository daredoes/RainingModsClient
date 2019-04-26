import logging
import json
import os
import glob
from websocket_server import WebsocketServer

user = None

class User(object):
    """
    This class is a singleton object representing the person running this script's desktop environment.
    """
    mods = []


def new_client(client, server):
	server.send_message(client, make_message_for_client('data', 'update'))

def make_message_for_client(message, action='update', data=None):
    return json.dumps({
        'action': action,
        'message': message,
        'data': data,
    })

def message_received(client, server, message):
    try:
        msg_data = json.loads(message)
        action, message, data = msg_data.get('action'), msg_data.get('message'), msg_data.get('data')
        server.send_message(client, make_message_for_client('Successfully read message', 'info'))
    except (json.JSONDecodeError, KeyError) as e:
        server.send_message(client, make_message_for_client('Cannot read message: {}'.format(e), 'info'))
    

server = WebsocketServer(13254, host='127.0.0.1', loglevel=logging.INFO)
server.set_fn_new_client(new_client)
server.set_fn_message_received(message_received)
server.run_forever()
