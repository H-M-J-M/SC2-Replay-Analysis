
import mpyq
import json
from pathlib import Path
from io import BytesIO

def get_replay_info(replay_path: str | Path):
    with Path(replay_path).open("rb") as f:
        replay_data = f.read()
        replay_io = BytesIO()
        replay_io.write(replay_data)
        replay_io.seek(0)
        archive = mpyq.MPQArchive(replay_io).extract()
        metadata = json.loads(archive[b"replay.gamemetadata.json"].decode("utf-8"))
        print(json.dumps(metadata, indent=4))

if __name__ == "__main__":
    replay_name = "Replays/4299043_Xena_negativeZero_LeyLinesAIE_v3.SC2Replay"
    folder_path = Path(__file__).parent
    replay_path = folder_path / replay_name
    get_replay_info(replay_path)
