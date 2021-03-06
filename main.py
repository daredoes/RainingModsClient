import logging
import json
import os
import shutil
import subprocess
import sys
import time
import glob
import wget
from websocket_server import WebsocketServer
import tkinter as tk
from tkinter import filedialog
import zipfile

def is_64_bit_windows():
    return 'PROGRAMFILES(X86)' in os.environ

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
        author_data = data[author_id]
        mod = ModAuthor(author_id, current_user, author_data.get('name'), author_data.get('url'))
        for repo_id in author_data.get('repos', {}):
            repo_data = author_data['repos'][repo_id]
            repo = ModRepo(repo_id, repo_data.get('name'), repo_data.get('url'), repo_data.get('readme'), repo_data.get('description'))
            release_data = repo_data.get('release', {})
            release = ModRelease(release_data.get('id'), release_data.get('name'), release_data.get('tag_name'), release_data.get('url'), release_data.get('updated_at'))
            for asset_id in release_data.get('assets', {}):
                asset_data = release_data['assets'][asset_id]
                asset = ModReleaseAsset(asset_id, asset_data.get('download'), asset_data.get('path'), asset_data.get('name'), asset_data.get('content_type'))
                release.add_asset(asset)
            repo.add_release(release)
            mod.add_repo(repo)
        mods.append(mod)
    return mods


class ModAuthor(object):
    def __init__(self, git_id, user, name, url):
        self.id = git_id
        self.user = user
        self.repos = []
        self.name = name
        self.url = url

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
            self.id: {
                'name': self.name,
                'url': self.url,
                'id': self.id,
                'repos': repos,
            }
        }

    def install(self):
        logger.info('Starting install of {}'.format(self.name))
        for child in self.children:
            child.install()
        logger.info('Finalizing install of {}'.format(self.name))
        plugin_root = self.user.plugin_path
        plugin_path = os.path.join(plugin_root, self.name)
        os.makedirs(plugin_path, exist_ok=True)
        json.dump(self.to_dict(), open(os.path.join(plugin_path, 'RainingMods.json'), 'w'), sort_keys=True, indent=4, separators=(',', ': '))
        logger.info('Ended install of {}'.format(self.name))

    def uninstall(self):
        logger.info('Starting uninstall of {}'.format(self.name))
        plugin_root = self.user.plugin_path
        plugin_path = os.path.join(plugin_root, self.name)
        shutil.rmtree(plugin_path, ignore_errors=True)
        logger.info('Finalizing uninstall of {}'.format(self.name))
        del self.repos
        self.repos = []
        logger.info('Ended uninstall of {}'.format(self.name))

    def uninstall_repository(self, repository_id):
        i = -1
        for j, repo in enumerate(self.repos):
            if repo.id == repository_id:
                i = j
                break

        if i != -1:
            logger.info('Starting uninstall of {}'.format(self.name))
            plugin_root = self.user.plugin_path
            plugin_path = os.path.join(plugin_root, self.name, repo.name)
            shutil.rmtree(plugin_path, ignore_errors=True)
            logger.info('Finalizing uninstall of {}'.format(self.name))
            del self.repos[i]
            logger.info('Ended uninstall of {}'.format(self.name))

            if len(self.repos) == 0:
                logger.info('Uninstalling author as there are no repostiories left')
                self.user.uninstall_author(self.id)

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
    def __init__(self, git_id, name, url, readme, description):
        self.id = git_id
        self.release = None
        self.name = name
        self.url = url
        self.readme = readme
        self.description = description
        self.author = None

    def add_release(self, release):
        if isinstance(release, ModRelease):
            if release != self:
                release.repo = self
                self.release = release
    
    def to_dict(self):
        return {
            self.id: {
                'release': self.release.to_dict() if self.release else {},
                'name': self.name,
                'url': self.url,
                'readme': self.readme,
                'description': self.description,
                'id': self.id,
            }
        }

    def install(self):
        for child in self.children:
            child.install()

    @property
    def children(self):
        return [self.release]

    def __cmp__(self, other):
        if isinstance(other, self.__class__):        
            try:
                if self.id == other.id:
                    if self.children == other.children:
                        return True
            except Exception:
                return False

class ModRelease(object):
    def __init__(self, git_id, name, tag_name, url, updated_at):
        self.id = git_id
        self.assets = []
        self.name = name
        self.tag_name = tag_name
        self.url = url
        self.updated_at = updated_at
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
            'assets': assets,
            'id': self.id,
            'name': self.name,
            'tag_name': self.name,
            'url': self.url,
            'updated_at': self.updated_at
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
    
    def __init__(self, git_id, download_url, name, content_type, path=None):
        self.id = git_id
        self.download_url = download_url
        self._path = path
        self.name = name
        self._content_type = content_type
        self.release = None

    def to_dict(self):
        return {
            self.id: {
                'path': self._path,
                'download': self.download_url,
                'name': self.name,
                'id': self.id,
            }
        }

    def install(self):
        if self.release and self.release.repo and self.release.repo.author and self.release.repo.author.user and self.release.repo.author.user.has_bepin:
            plugin_root = self.release.repo.author.user.plugin_path
            plugin_path = os.path.join(plugin_root, self.release.repo.author.name, self.release.repo.name)
            os.makedirs(plugin_path, exist_ok=True)
            for path in os.listdir(plugin_path):
                logger.info(path)
                full_path = os.path.join(plugin_path, path)
                if os.path.isfile(full_path):
                    os.remove(full_path)
                else:
                    shutil.rmtree(full_path, ignore_errors=True)
            plugin_path = os.path.join(plugin_path, self.release.name)
            os.makedirs(plugin_path, exist_ok=True)
            self._path = wget.download(self.download_url, plugin_path)
            if self._path.endswith('.zip'):
                with zipfile.ZipFile(self._path, 'r') as zip_ref:
                    zip_ref.extractall(plugin_path)

        
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
        self.install_bepin()

    def install_bepin(self):
        download_url = 'https://github.com/daredoes/BepInExPack/releases/download/1.3.1/BepInExPack.zip'
        path_to_zip_file = wget.download(download_url, out=self._path)
        zip_ref = zipfile.ZipFile(path_to_zip_file, 'r')
        zip_ref.extractall(self._path)
        zip_ref.close()
        os.remove(path_to_zip_file)
        self.set_path(self._path)

    def uninstall_author(self, author_id):
        i = -1
        for j, author in enumerate(self.mods):
            if author.id == author_id:
                i = j
                author.uninstall()
                break
        if i != -1:
            del self.mods[i]

    def uninstall_repository(self, author_id, repository_id):
        for author in self.mods:
            if author.id == author_id:
                author.uninstall_repository(repository_id)
                break

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
        self.is_in_correct_folder = True if len(self.files) else False
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
        if self.is_in_correct_folder and self.has_bepin:
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
    for mod in convert_mod_data_to_object(args, user):
        user.add_mod(mod, install=True)
    get_user_data(server, client)

def uninstall_mod_version(server, client, data, **args):
    for owner_id, repository_id in data.items():
        user.uninstall_repository(owner_id, repository_id)
    get_user_data(server, client)
            

actions = {
    'updateRootFolder': update_root_folder,
    'getUserData': get_user_data,
    'install': install_mod_version,
    'uninstall': uninstall_mod_version,
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


def main():
    while not user.is_in_correct_folder:
        if not pick_root_folder():
            logger.info('Sleeping for 2 seconds. Quit now, or select the folder where Risk of Rain 2.exe is located.')
            time.sleep(2)
    server = WebsocketServer(13254, host='127.0.0.1', loglevel=logging.INFO)
    server.set_fn_new_client(new_client)
    server.set_fn_message_received(message_received)
    server.run_forever()


if __name__ == '__main__':
    while not user.is_in_correct_folder:
        if not pick_root_folder():
            logger.info('Sleeping for 2 seconds. Quit now, or select the folder where Risk of Rain 2.exe is located.')
            time.sleep(2)
    server = WebsocketServer(13254, host='127.0.0.1', loglevel=logging.INFO)
    server.set_fn_new_client(new_client)
    server.set_fn_message_received(message_received)
    server.run_forever()