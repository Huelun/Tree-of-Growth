import datetime
import os
import pickle
from collections import defaultdict
from enum import Enum
from typing import Iterator


class SizeReserveRule(Enum):
    """Defines the operational modes for the Size Reserve mechanic within a universe."""
    ENABLED = "enabled"  # Default: Fully functional for everyone
    DISABLED = "disabled"  # Completely turned off for the entire universe
    TALENT_REQUIRED = "talent"  # Active, but players must possess a specific talent to use it


class MarketOffer:
    def __init__(self, seller_id: str, item, price, listed_at: datetime = None):
        self.seller_id = seller_id  # ID of the player who gets paid upon sale
        self.item = item
        self.price = price
        self.listed_at = listed_at or datetime.datetime.utcnow()  # Timestamp for automatic cleanup


class Market:
    def __init__(self):
        self.offers: list[MarketOffer] = []

    def list_item(self, seller_id: str, item: "Item", price):
        offer = MarketOffer(seller_id, item, price)
        self.offers.append(offer)

    def remove_offer(self, offer: MarketOffer):
        if offer in self.offers:
            self.offers.remove(offer)


class Universe:
    def __init__(self, name):
        from player import Player
        self.name = name
        self.players: set[Player] = set()
        self.market = Market()

        # Centralized game rules and coefficients
        self.rules = {
            "metabolic_rate": 1.0,  # Metabolic rate multiplier (e.g., 1.0 is standard, 2.0 is twice as fast)
            "belly_rubs_stack": False,

            # NEW: Size Reserve rule configuration with its three options (Default: TALENT_REQUIRED)
            "size_reserve": SizeReserveRule.TALENT_REQUIRED,
        }

    def get_main_channel(self):
        return multiverse_instance.get_main_channel(self)

    def send_to_main_channel(self, message: str) -> bool:
        """
        Wysyła wiadomość na główny kanał tego uniwersum, bezpiecznie
        z dowolnego wątku (np. z pętli tasks.loop w cogu).
        Zwraca True, jeśli wysyłka została zlecona, False jeśli się nie udało
        (np. brak kanału, brak klienta, brak działającej pętli).
        """
        main_channel_id = self.get_main_channel()
        if not main_channel_id:
            return False

        client = multiverse_instance.discord_client
        if not client or not client.loop or not client.loop.is_running():
            return False

        channel = client.get_channel(main_channel_id)
        if not channel:
            return False

        import asyncio
        asyncio.run_coroutine_threadsafe(channel.send(message), client.loop)
        return True

    def get_player_by_id(self, player_id):
        for grower in self.players:
            if grower.id == player_id:
                return grower
        return None

    def update_rule(self, rule_name: str, value):
        """
        Updates a game rule safely.
        """
        if rule_name in self.rules:
            # Basic type validation based on existing value
            expected_type = type(self.rules[rule_name])
            try:
                self.rules[rule_name] = expected_type(value)
                return True
            except ValueError:
                return False
        return False

    def get_rule(self, rule_name: str, default=None):
        """
        Retrieves a rule value.
        """
        return self.rules.get(rule_name, default)


class GuildData:
    def __init__(self, guild_id):
        self.guild_id = guild_id
        self.main_channel_id = None


class Multiverse:
    def __iter__(self) -> Iterator["Universe"]:
        return iter(self.universe_to_id.keys())

    def __init__(self):
        self.guilds = {}
        self.universe_to_id = {}
        self.id_to_universe = {}
        self.discord_client = None

    def set_discord_client(self, client):
        """Wywoływane raz, z main.py, zaraz po utworzeniu klienta bota."""
        self.discord_client = client

    def __getstate__(self):
        """Wyklucza niepicklowalne/przejściowe obiekty z zapisu."""
        state = self.__dict__.copy()
        state['discord_client'] = None  # nigdy nie zapisujemy referencji do bota
        return state

    def __setstate__(self, state):
        """Po wczytaniu discord_client jest None, dopóki main.py go nie ustawi ponownie."""
        self.__dict__.update(state)
        # discord_client zostaje None — set_discord_client() musi być wywołane
        # ponownie po wczytaniu (dokładnie tak samo, jak przy pierwszym starcie)

    @property
    def universes(self):
        """
        Returns a view of all tracked Universe instances.
        Provides an easy way to iterate over all universes in the multiverse.
        """
        return self.universe_to_id.keys()

    def create_universe(self, channel_id, name: str):
        """Creates a new universe and associates it with a channel."""
        self.add_id(Universe(name), channel_id)

    def remove_universe(self, universe: "Universe"):
        channels = self.universe_to_id.pop(universe, None)

        if not channels:
            return

        for channel_id in channels:
            self.id_to_universe.pop(channel_id, None)

    def add_universe(self, universe: "Universe"):
        """Adds a universe if it's not already tracked."""
        if universe not in self.universe_to_id:
            self.universe_to_id[universe] = []

    def add_id(self, universe: "Universe", channel_id):
        """Associates a universe with a channel ID."""
        self.add_universe(universe)
        if channel_id not in self.universe_to_id[universe]:
            self.universe_to_id[universe].append(channel_id)
            self.id_to_universe[channel_id] = universe

    def add_channel(self, universe: "Universe", channel_id):
        if universe not in self.universe_to_id:
            raise ValueError("Universe does not exist.")

        if channel_id in self.id_to_universe:
            raise ValueError("Channel already assigned to a universe.")

        self.universe_to_id[universe].append(channel_id)
        self.id_to_universe[channel_id] = universe

    def remove_channel(self, universe: "Universe", channel_id):
        channels = self.universe_to_id.get(universe)

        if not channels:
            raise ValueError("Universe does not exist.")

        if channel_id not in channels:
            raise ValueError("Channel not associated with this universe.")

        if len(channels) == 1:
            raise ValueError("Cannot remove the last channel of a universe.")

        channels.remove(channel_id)
        self.id_to_universe.pop(channel_id, None)

    def set_main_channel(self, universe: "Universe", channel_id):
        channels = self.universe_to_id.get(universe)

        if not channels:
            raise ValueError("Universe does not exist.")

        if channel_id not in channels:
            raise ValueError("Channel not associated with this universe.")

        channels.remove(channel_id)
        channels.insert(0, channel_id)

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

    def get_universes(self):
        return self.universe_to_id.keys()

    def get_channels(self, universe: "Universe"):
        return self.universe_to_id.get(universe, [])

    def get_main_channel(self, universe: "Universe"):
        channels = self.get_channels(universe)
        return channels[0] if channels else None


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

    temp_universe = Universe("temp")
    default_rules = temp_universe.rules.copy()

    multiverse_instance.__dict__.update(loaded_data.__dict__)

    for uni in multiverse_instance.universes:
        # --- POST-LOAD UNIVERSE MARKET REPAIR ---
        if not hasattr(uni, 'market') or uni.market is None:
            uni.market = Market()
        else:
            # Ensure all offers on the market have the nsfw attribute
            if hasattr(uni.market, 'offers') and uni.market.offers:
                for offer in uni.market.offers:
                    if offer.item and not hasattr(offer.item, 'nsfw'):
                        offer.item.nsfw = False

        if not hasattr(uni, 'rules'):
            uni.rules = default_rules.copy()
        else:
            merged = default_rules.copy()
            merged.update(uni.rules)
            uni.rules = merged

        if hasattr(uni, 'players') and isinstance(uni.players, set):
            for player in uni.players:
                if not hasattr(player, '_fitness'):
                    player._fitness = 1.0

                if not hasattr(player, '_size_reserve'):
                    player._size_reserve = 0.0

                # --- POST-LOAD PLAYER INVENTORY NSFW, CREATOR & PORTION REPAIR ---
                inventory = getattr(player, 'inventory', None)
                if inventory:
                    for item in inventory:
                        if not hasattr(item, 'nsfw'):
                            item.nsfw = False
                        if not hasattr(item, 'creator_id'):
                            item.creator_id = None
                        if not hasattr(item, 'min_portion_pct'):
                            item.min_portion_pct = 0.00

                if hasattr(player, 'effects') and player.effects:
                    for e in player.effects:
                        e.stackable = e.effect_type.stackable

                if not hasattr(player, 'talent_points'):
                    player.talent_points = 1
                if not hasattr(player, 'talent_refund_points'):
                    player.talent_refund_points = 1
                if not hasattr(player, 'talents'):
                    player.talents = {}

                if hasattr(player, 'body') and isinstance(player.body, dict):
                    key_mapping = {
                        'front_l': 'front_leg_l',
                        'front_r': 'front_leg_r',
                        'back_l': 'back_leg_l',
                        'back_r': 'back_leg_r'
                    }
                    for old_key, new_key in key_mapping.items():
                        if old_key in player.body and new_key not in player.body:
                            player.body[new_key] = player.body.pop(old_key)

    print(
        f"Data of {multiverse_instance.get_player_count()} players loaded "
        f"for {multiverse_instance.get_universe_count()} universes."
    )
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
