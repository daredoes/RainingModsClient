import logging
import json
import os
import shutil
import time
import glob
import wget
from websocket_server import WebsocketServer
import tkinter as tk
from tkinter import filedialog

import ctypes, sys

def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

root = tk.Tk()
root.withdraw()

user = None

logger = logging.getLogger(__name__)
logging.basicConfig()

logger.setLevel(logging.INFO)

files_in_risk_of_rain_2_root_folder = ["Risk of Rain 2.exe", "Risk of Rain 2_Data"]
files_in_risk_of_rain_2_root_folder_with_bepin = ["winhttp.dll", "BepInEx"]

def convert_mod_data_to_object(data, current_user):
    mods = []
    for author_id in data.keys():
        mod = ModAuthor(author_id, current_user)
        for repo_id in data[author_id]:
            repo = ModRepo(repo_id)
            for release_id in data[author_id][repo_id]:
                release = ModRelease(release_id)
                for asset_id in data[author_id][repo_id][release_id]:
                    asset_data = data[author_id][repo_id][release_id][asset_id]
                    asset = ModReleaseAsset(asset_id, asset_data['download'], asset_data['path'])
                    release.add_asset(asset)
                repo.add_release(release)
            mod.add_repo(repo)
        mods.append(mod)
    return mods


class ModAuthor(object):
    def __init__(self, id, user):
        self.id = id
        self.user = user
        self.repos = []

    def add_repo(self, repo):
        if isinstance(repo, ModRepo):
            if repo not in self.repos:
                repo.author = self
                self.repos.append(repo)
    
    def to_dict(self):
        repos = {}
        for repo in self.repos:
            repos.update(repo.to_dict())
        return {
            self.id: repos
        }

    def install(self):
        logger.info('Starting install of {}'.format(self.id))
        for child in self.children:
            child.install()
        logger.info('Finalizing install of {}'.format(self.id))
        plugin_root = self.user.plugin_path
        plugin_path = os.path.join(plugin_root, self.id)
        os.makedirs(plugin_path, exist_ok=True)
        json.dump(self.to_dict(), open(os.path.join(plugin_path, 'RainingMods.json'), 'w'), sort_keys=True, indent=4, separators=(',', ': '))
        logger.info('Ended install of {}'.format(self.id))

    @property
    def children(self):
        return self.repos

    def __cmp__(self, other):
        if isinstance(other, self.__class__):        
            try:
                if self.id == other.id:
                    if self.children == other.children:
                        return True
            except Exception:
                return False
    
class ModRepo(object):
    def __init__(self, id):
        self.id = id
        self.releases = []
        self.author = None

    def add_release(self, release):
        if isinstance(release, ModRelease):
            if release not in self.releases:
                release.repo = self
                self.releases.append(release)
    
    def to_dict(self):
        releases = {}
        for release in self.releases:
            releases.update(release.to_dict())
        return {
            self.id: releases
        }

    def install(self):
        for child in self.children:
            child.install()

    @property
    def children(self):
        return self.releases

    def __cmp__(self, other):
        if isinstance(other, self.__class__):        
            try:
                if self.id == other.id:
                    if self.children == other.children:
                        return True
            except Exception:
                return False

class ModRelease(object):
    def __init__(self, id):
        self.id = id
        self.assets = []
        self.repo = None

    def add_asset(self, asset):
        if isinstance(asset, ModReleaseAsset):
            if asset not in self.assets:
                asset.release = self
                self.assets.append(asset)

    def to_dict(self):
        assets = {}
        for asset in self.assets:
            assets.update(asset.to_dict())
        return {
            self.id: assets
        }

    def install(self):
        for child in self.children:
            child.install()
    
    @property
    def children(self):
        return self.assets

    def __cmp__(self, other):
        if isinstance(other, self.__class__):        
            try:
                if self.id == other.id:
                    if self.children == other.children:
                        return True
            except Exception:
                return False

class ModReleaseAsset(object):
    
    def __init__(self, id, download_url, path=None):
        self.id = id
        self.download_url = download_url
        self._path = path
        self.release = None

    def to_dict(self):
        return {
            self.id: {
                'path': self._path,
                'download': self.download_url
            }
        }

    def install(self):
        if self.release and self.release.repo and self.release.repo.author and self.release.repo.author.user and self.release.repo.author.user.has_bepin:
            plugin_root = self.release.repo.author.user.plugin_path
            plugin_path = os.path.join(plugin_root, self.release.repo.author.id, self.release.repo.id, self.release.id)
            shutil.rmtree(plugin_path, ignore_errors=True)
            os.makedirs(plugin_path, exist_ok=True)
            wget.download(self.download_url, plugin_path)
        
    def __cmp__(self, other):
        try:
            if self.id == other.id:
                return True
        except Exception:
            return False


class User(object):
    """
    This class is a singleton object representing the person running this script's desktop environment.
    """
    mods = []
    _path = ""
    files = []
    has_bepin = False
    is_in_correct_folder = False
    plugin_path = None

    def __init__(self):
        self.set_path('C:\\Program Files (x86)\\Steam\\steamapps\\common\\Risk of Rain 2')

    def check_and_create_mod_folder(self):
        if os.path.exists(self.plugin_path):
            return True
        else:
            os.mkdir(self.plugin_path)
            return False

    def add_mod(self, mod, install=False):
        if mod not in self.mods:
            if install:
                mod.install()
            self.mods.append(mod)

    def get_mods(self):
        if self.is_in_correct_folder:
            if self.has_bepin:
                glob_string = "{}\*\RainingMods.json".format(os.path.join(self._path, 'BepInEx', 'plugins', 'RainingMods'))
                logger.info(glob_string)
                for filename in glob.glob(glob_string):
                    logger.info(filename)
                    mod_data = json.load(open(filename, 'r'))
                    for mod in convert_mod_data_to_object(mod_data, self):
                        self.add_mod(mod)
        return self.mods

    def set_path(self, path):
        try:
            os.chdir(path)
        except (FileNotFoundError, OSError, TypeError):
            return False
        self._path = path
        self.plugin_path = os.path.join(self._path, 'BepInEx', 'plugins', 'RainingMods')
        
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
        if self.check_and_create_mod_folder():
            self.get_mods()
        return True

    def get_path(self):
        return self._path

    def __str__(self):
        mods = {}
        for mod in self.mods:
            mods.update(mod.to_dict())
        return json.dumps({
            'files': self.files,
            'has_bepin': self.has_bepin,
            'is_in_correct_folder': self.is_in_correct_folder,
            'mods': mods,
            'rootFolder': self._path
        })


file_path = None
user = User()

def pick_root_folder():
    file_path = filedialog.askdirectory(title="Select the folder where 'Risk of Rain 2_Data' is located",
                                        initialdir=user.get_path())
    return user.set_path(file_path)

def new_client(client, server):
    get_user_data(server, client)


def make_message_for_client(message, action='update', data=None):
    logger.info(message)
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
    
def get_user_data(server, client, **args):
    server.send_message(client, make_message_for_client('update', 'update', {'user': str(user)}))

def install_mod_version(server, client, **args):
    for author_id in args.keys():
        mod_author = ModAuthor(author_id, user)
        for repo_id in args[author_id]:
            mod_repo = ModRepo(repo_id)
            mod_author.add_repo(mod_repo)
            for release_id in args[author_id][repo_id]:
                mod_release = ModRelease(release_id)
                mod_repo.add_release(mod_release)
                for asset_id in args[author_id][repo_id][release_id]:
                    download_url = args[author_id][repo_id][release_id][asset_id]['download']
                    mod_asset = ModReleaseAsset(asset_id, download_url)
                    mod_release.add_asset(mod_asset)
        user.add_mod(mod_author, install=True)
    get_user_data(server, client)
            

actions = {
    'updateRootFolder': update_root_folder,
    'getUserData': get_user_data,
    'install': install_mod_version,
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



if __name__ == "__main__":
    if is_admin():
        # Code of your program here
        while not user.is_in_correct_folder:
            if not pick_root_folder():
                logger.info('Sleeping for 2 seconds. Quit now, or select the folder where Risk of Rain 2.exe is located.')
                time.sleep(2)
        server = WebsocketServer(13254, host='127.0.0.1', loglevel=logging.INFO)
        server.set_fn_new_client(new_client)
        server.set_fn_message_received(message_received)
        server.run_forever()
    else:
        # Re-run the program with admin rights
        ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, __file__, None, 1)


