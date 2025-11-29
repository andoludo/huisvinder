from pathlib import Path

from huisvinder.services import read_houses



if __name__ == "__main__":
    database_path = Path(__file__).parent.joinpath("building.db")
    read_houses(database_path)