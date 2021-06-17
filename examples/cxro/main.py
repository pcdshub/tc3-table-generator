import decimal
import pathlib
import sys

import pandas as pd

# Bad practices from the get-go, nice!
sys.path.insert(0, "../../")  # noqa

import plc_code

columns = {
    "E(eV)": "fEnergyEV",
    "f1": "f1",
    "f2": "f2",
}

dataframes = {}
for idx, fn in enumerate(pathlib.Path("data").glob("*.nff")):
    dataframes[fn.stem] = pd.read_csv(
        fn, delimiter="\t", converters={col: decimal.Decimal for col in columns}
    ).rename(columns=columns)
    # if idx == 1:
    #     break


print(
    plc_code.generate_lookup_table_source(
        fb_name="FB_AbsorptionLUT",
        dataframes=dataframes,
        table_prefix="fTable_",
        lookup_input="fEnergyEV",
    )
)
