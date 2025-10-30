import platform
import csv
from pathlib import Path

from loguru import logger

from sc2.main import run_replay
from sc2.observer_ai import ObserverAI
from sc2.data import Race


DATA_INTERVAL = 20  #Time between data records (in game steps)
DATA_START_TIME = 0 #Time to start gathering data (in seconds)
DATA_END_TIME = 120 #Time to stop gathering data (in seconds)

class ObserverBot(ObserverAI):
    def __init__(self, replay_path, observed_id):
        super().__init__()
        self.unit_data = []
        self.replay_path = replay_path
        self.observed_id = observed_id

    def _prepare_step(self, state, proto_game_info):
        self.race = Race.Terran #not sure why this is needed, but the program will crash without it.
        super()._prepare_step(state, proto_game_info)

    async def on_start(self):
        print(f"Replay on_start() was called for observed_id={self.observed_id}")

    async def on_step(self, iteration: int):
        if self.time > DATA_END_TIME:
            await self.client.leave()
            return

        if self.time < DATA_START_TIME:
            return
        
        if iteration % DATA_INTERVAL != 0:
            return

        for unit in self.all_units:
            
            try:
                owner = unit.owner_id
            except AttributeError:
                owner = 0

            self.unit_data.append(
                {
                    "timestamp": self.time,
                    "unit_tag": unit.tag,
                    "unit_type": unit.type_id.name,
                    "player_id": owner,
                    "position_x": unit.position.x,
                    "position_y": unit.position.y,
                    "health": unit.health,
                    "shield": unit.shield,
                    "energy": unit.energy,
                    "build_progress": unit.build_progress,
                    "resource_remaining": unit.mineral_contents if unit.is_mineral_field  else (unit.vespene_contents if unit.is_vespene_geyser else 0),
                }
            )

    async def on_end(self, game_result):
        if not self.unit_data:
            print("No unit data to write.")
            return

        # Group data by player_id
        player_data = {}
        for row in self.unit_data:
            player_id = row["player_id"]
            if player_id not in player_data:
                player_data[player_id] = []
            player_data[player_id].append(row)

        replay_name_parts = Path(self.replay_path).stem.split("_")
        game_number = replay_name_parts[0]
        player_1_name = replay_name_parts[1]
        player_2_name = replay_name_parts[2]
        map_name = "_".join(replay_name_parts[3:])
        
        observer_name = player_1_name if self.observed_id == 1 else player_2_name

        output_dir = Path("Output") / game_number
        output_dir.mkdir(parents=True, exist_ok=True)

        for player_id, data in player_data.items():

            if player_id in [1, 2]:
                player_name = player_1_name if player_id == 1 else player_2_name
                if player_id == self.observed_id:
                    output_filename = f"{game_number}_{player_name}_{map_name}_ground-truth.csv"
                else:
                    output_filename = f"{game_number}_{player_name}_{map_name}_observed-by-{observer_name}.csv"
            else:
                output_filename = f"{game_number}_player-id-{player_id}_{map_name}_observed-by-{observer_name}.csv" #These are (probably) neutral objects on the map (e.g., minerals).
            
            output_file = output_dir / output_filename

            with open(output_file, "w", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=data[0].keys())
                writer.writeheader()
                writer.writerows(data)
            print(f"Successfully wrote unit data for player {player_id} to {output_file}")

    async def on_unit_destroyed(self, unit_tag):
        pass

    async def on_unit_created(self, unit):
        pass

    async def on_unit_took_damage(self, unit, amount):
        pass

    async def on_unit_type_changed(self, unit, previous_type):
        pass

    async def on_building_construction_started(self, unit):
        pass

    async def on_building_construction_complete(self, unit):
        pass

    async def on_upgrade_complete(self, upgrade):
        pass

    async def on_enemy_unit_entered_vision(self, unit):
        pass

    async def on_enemy_unit_left_vision(self, unit_tag):
        pass

if __name__ == "__main__":
    replay_name = "Replays/4299043_Xena_negativeZero_LeyLinesAIE_v3.SC2Replay"
    if platform.system() == "Linux":
        home_replay_folder = Path.home() / "Documents" / "StarCraft II" / "Replays"
        replay_path = home_replay_folder / replay_name
        if not replay_path.is_file():
            logger.warning(f"You are on linux, please put the replay in directory {home_replay_folder} (untested)")
            raise FileNotFoundError
    elif Path(replay_name).is_absolute():
        replay_path = Path(replay_name)
    else:
        folder_path = Path(__file__).parent
        replay_path = folder_path / replay_name
    assert replay_path.is_file(), (
        "Replay not found. Put an SC2Replay file in the Replays folder, then run again."
    )
    
    # Run analysis for Player 1's perspective
    observer_1 = ObserverBot(replay_path, observed_id=1)
    run_replay(observer_1, replay_path=str(replay_path), observed_id=1)

    # Run analysis for Player 2's perspective
    observer_2 = ObserverBot(replay_path, observed_id=2)
    run_replay(observer_2, replay_path=str(replay_path), observed_id=2)