import logging
import json
import os
import glob
from websocket_server import WebsocketServer

user = None

files_in_risk_of_rain_2_root_folder = ["Risk of Rain 2.exe", "Risk of Rain 2_Data"]
files_in_risk_of_rain_2_root_folder_with_bepin = ["winhttp.dll", "BepInEx"]

class User(object):
    """
    This class is a singleton object representing the person running this script's desktop environment.
    """
    mods = []
    _path = ""
    files = []
    has_bepin = False
    is_in_correct_folder = False

    def set_path(self, path):
        try:
            os.chdir(path)
        except (FileNotFoundError, OSError):
            return False
        self._path = path
        
        self.files = glob.glob('*')
        self.is_in_correct_folder = True
        self.has_bepin = True
        for filename in files_in_risk_of_rain_2_root_folder:
            if filename not in self.files:
                self.is_in_correct_folder = False
        if not self.is_in_correct_folder:
            self.has_bepin = False
        else:
            for filename in files_in_risk_of_rain_2_root_folder_with_bepin:
                if filename not in self.files:
                    self.has_bepin = False
        return True

    def get_path(self):
        return self._path

    def __str__(self):
        return json.dumps({
            'files': self.files,
            'has_bepin': self.has_bepin,
            'is_in_correct_folder': self.is_in_correct_folder,
            'mods': self.mods,
            'rootFolder': self._path
        })

user = User()


def new_client(client, server):
	server.send_message(client, make_message_for_client('data', 'update'))


def make_message_for_client(message, action='update', data=None):
    return json.dumps({
        'action': action,
        'message': message,
        'data': data,
    })

def update_root_folder(folder, server, client, **args):
    if user.set_path(folder):
        server.send_message(client, make_message_for_client('rootFolder', data={'user': str(user)}))
    else:
        server.send_message(client, make_message_for_client('Failed to read path', 'info'))

actions = {
    'updateRootFolder': update_root_folder
}

def message_received(client, server, message):
    try:
        msg_data = json.loads(message)
        action, message, data = msg_data.get('action'), msg_data.get('message'), msg_data.get('data', {})
        
        func = actions.get(action)
        if func:
            data.update({'server': server, 'client': client})
            func(**data)
        else:
            server.send_message(client, make_message_for_client('Successfully read message', 'info', {'data': msg_data}))
    except (json.JSONDecodeError, KeyError) as e:
        server.send_message(client, make_message_for_client('Cannot read message: {}'.format(e), 'info'))
    

server = WebsocketServer(13254, host='127.0.0.1', loglevel=logging.INFO)
server.set_fn_new_client(new_client)
server.set_fn_message_received(message_received)
server.run_forever()

