import os
import pickle
import datetime

import player


class Universe:
    def __init__(self, name):
        self.name = name
        self.players: set(player.Player) = set()


class GuildData:
    def __init__(self, guild_id):
        self.guild_id = guild_id
        self.main_channel_id = None


class Multiverse:
    def __init__(self):
        #  self.universes = {}
        self.guilds = {}
        # Dictionary to store channel ids associated with universes
        self.universe_to_id = {}
        self.id_to_universe = {}

    def create_universe(self, channel_id, name: str):
        self.add_id(Universe(name), channel_id)

    def add_universe(self, universe: Universe):
        if universe not in self.universe_to_id:
            self.universe_to_id[universe] = []

    def add_id(self, universe: Universe, channel_id):
        self.add_universe(universe)
        if channel_id not in self.universe_to_id[universe]:
            self.universe_to_id[universe].append(channel_id)
            self.id_to_universe[channel_id] = universe

    def get_universe_from_id(self, channel_id):
        return self.id_to_universe.get(channel_id, None)

    def get_universe_count(self):
        return len(self.universe_to_id)

    def get_guild_count(self):
        return len(self.guilds)

    def get_player_count(self):
        count = 0
        for u in self.universe_to_id:
            count += len(u.players)
        return count


multiverse_instance = Multiverse()
save_directory = "saves"


def save_data():
    print("Saving data")
    if not os.path.exists(save_directory):
        os.makedirs(save_directory)
    date = datetime.datetime.now().strftime("%Y_%j_%H%M%S")
    filename = "save_data" + date + ".pkl"
    file_path = os.path.join(save_directory, filename)
    with open(file_path, 'wb') as file:
        pickle.dump(multiverse_instance, file)
        print("Data of " + str(multiverse_instance.get_universe_count()) + " universes saved as " + filename)


def load_most_recent_save():
    directory = "./" + save_directory
    files = os.listdir(directory)
    save_files = [f for f in files if f.endswith(".pkl")]
    if not save_files:
        print("No save files found")
        return None

    save_files.sort(key=lambda f: os.path.getmtime(os.path.join(directory, f)), reverse=True)
    most_recent_save = save_files[0]
    load_data(most_recent_save)


def load_data(save_file):
    print("Loading data")
    with open(os.path.join(save_directory, save_file), 'rb') as file:
        loaded_data = pickle.load(file)
    multiverse_instance.__dict__.update(loaded_data.__dict__)
    print(
        "Data of " + str(multiverse_instance.get_player_count()) + " players loaded for " + str(
            multiverse_instance.get_universe_count()) + " universes.")
