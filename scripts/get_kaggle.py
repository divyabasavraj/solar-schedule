"""Download the Kaggle "Solar Power Generation Data" (two Indian plants, 34 days)
and save it as tidy Parquet in data/raw/kaggle/ (git-ignored: not ours to
redistribute; anyone can re-run this with their own Kaggle token).

    uv run python scripts/get_kaggle.py

Known quirks, kept as is here and handled in milestone 3:
* Plant 1 generation writes dates as DD-MM-YYYY HH:MM; the other three files
  as YYYY-MM-DD HH:MM:SS. Each file is parsed with its own explicit format.
* Plant 1 DC_POWER is about 10x AC_POWER (a units issue widely noted on the
  dataset's Kaggle page); Plant 2 DC and AC are on the same scale.
* IRRADIATION is in kW/m2 averaged over the 15 minutes; power is in kW.
"""

from pathlib import Path

import kagglehub
import pandas as pd

from solarschedule.store import RAW, write

DATASET = "anikannal/solar-power-generation-data"
FORMATS = {
    "Plant_1_Generation_Data.csv": "%d-%m-%Y %H:%M",
    "Plant_2_Generation_Data.csv": "%Y-%m-%d %H:%M:%S",
    "Plant_1_Weather_Sensor_Data.csv": "%Y-%m-%d %H:%M:%S",
    "Plant_2_Weather_Sensor_Data.csv": "%Y-%m-%d %H:%M:%S",
}


def load(folder: Path, name: str) -> pd.DataFrame:
    df = pd.read_csv(folder / name)
    df.columns = df.columns.str.lower()
    df["time_ist"] = pd.to_datetime(df.pop("date_time"), format=FORMATS[name])
    df["plant"] = int(name.split("_")[1])
    return df.rename(columns={"plant_id": "plant_code"})


def main() -> None:
    folder = Path(kagglehub.dataset_download(DATASET))
    out = RAW / "kaggle"
    for kind in ("Generation_Data", "Weather_Sensor_Data"):
        df = pd.concat([load(folder, f"Plant_{p}_{kind}.csv") for p in (1, 2)], ignore_index=True)
        df = df.sort_values(["plant", "time_ist", "source_key"], ignore_index=True)
        path = write(df, out / ("generation.parquet" if kind.startswith("Gen") else "weather.parquet"))
        print(f"wrote {path.relative_to(RAW)}  {len(df):>6} rows  {df.time_ist.min()} .. {df.time_ist.max()}")


if __name__ == "__main__":
    main()
