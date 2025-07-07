import datetime
import os
import pickle
from collections import defaultdict
from typing import List


class Universe:
    def __init__(self, name):
        from player import Player
        self.name = name
        self.players: set[Player] = set()

    def get_player_by_id(self, player_id):
        for grower in self.players:
            if grower.id == player_id:
                return grower
        return None


class GuildData:
    def __init__(self, guild_id):
        self.guild_id = guild_id
        self.main_channel_id = None


class Multiverse:
    def __init__(self):
        self.guilds = {}  # Unclear what this is used for, leaving it unchanged
        self.universe_to_id = {}  # Maps Universe instances to a list of associated channel IDs
        self.id_to_universe = {}  # Maps channel IDs back to Universe instances

    def create_universe(self, channel_id, name: str):
        """Creates a new universe and associates it with a channel."""
        self.add_id(Universe(name), channel_id)

    def add_universe(self, universe: Universe):
        """Adds a universe if it's not already tracked."""
        if universe not in self.universe_to_id:
            self.universe_to_id[universe] = []

    def add_id(self, universe: Universe, channel_id):
        """Associates a universe with a channel ID."""
        self.add_universe(universe)
        if channel_id not in self.universe_to_id[universe]:
            self.universe_to_id[universe].append(channel_id)
            self.id_to_universe[channel_id] = universe

    def get_universe_from_id(self, channel_id):
        """Retrieves a universe using a channel ID."""
        return self.id_to_universe.get(channel_id, None)

    def get_universe_count(self):
        """Returns the number of universes."""
        return len(self.universe_to_id)

    def get_guild_count(self):
        """Returns the number of guilds."""
        return len(self.guilds)

    def get_player_count(self):
        """Returns the total number of players across all universes."""
        return sum(len(u.players) for u in self.get_universes())

    def update_player_instances(self):
        """Ensures all players have their unit systems set up properly."""
        from cogs.effect import Effect
        from cogs.item import Item
        for u in self.get_universes():
            for p in u.players:
                if not hasattr(p, "inventory"):
                    p.inventory: List[Item] = []
                if not hasattr(p, "effects"):
                    p.effects: List[Effect] = []
                for i in p.inventory:
                    if not hasattr(i, "emoji"):
                        i.emoji = ""

    def get_universes(self):
        """Returns a list of all universes currently stored."""
        return list(self.universe_to_id.keys())

    def __iter__(self):
        """Allows iteration over universes directly with `for u in multiverse_instance`."""
        return iter(self.get_universes())


# Singleton instance of Multiverse
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
    print("Loaded most recent save")


def load_data(save_file):
    print("Loading data")
    with open(os.path.join(save_directory, save_file), 'rb') as file:
        loaded_data = pickle.load(file)
    multiverse_instance.__dict__.update(loaded_data.__dict__)
    multiverse_instance.update_player_instances()
    print(
        "Data of " + str(multiverse_instance.get_player_count()) + " players loaded for " + str(
            multiverse_instance.get_universe_count()) + " universes.")
    delete_old_files()


def delete_old_files():
    # Get the current time
    now = datetime.datetime.now()
    cutoff = now - datetime.timedelta(days=1)  # Define the cutoff as 24 hours ago

    # List all .pkl files in the save directory
    save_files = [f for f in os.listdir(save_directory) if f.endswith(".pkl")]

    # Group files by day (using day number and year as keys)
    files_by_day = defaultdict(list)
    for file in save_files:
        file_path = os.path.join(save_directory, file)
        file_time = datetime.datetime.fromtimestamp(os.path.getmtime(file_path))

        # Only consider files older than the cutoff for potential deletion
        if file_time < cutoff:
            day_key = file_time.strftime("%Y_%j")  # Year and day of the year
            files_by_day[day_key].append((file, file_time))

    # Process each day, keeping only the most recent file
    for day, files in files_by_day.items():
        # Sort files by modification time (the newest last)
        files.sort(key=lambda x: x[1])

        # Keep the most recent file and delete the rest
        for file, _ in files[:-1]:  # Exclude the most recent file
            os.remove(os.path.join(save_directory, file))
            print(f"Deleted old file: {file}")

    print("Old files deleted, keeping one file per day.")
