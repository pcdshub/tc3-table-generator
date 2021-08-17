import decimal
import pathlib
import sys

import pandas as pd
import tc3tg

columns = {
    "E(eV)": "fEnergyEV",
    "f1": "f1",
    "f2": "f2",
}

included_materials = {
    "Al",
    "Be",
    "C",
    "Ge",
    "Si",
}

dataframes = {}
for idx, fn in enumerate(pathlib.Path("data").glob("*.nff")):
    identifier = fn.stem.capitalize()
    if identifier in included_materials:
        dataframes[identifier] = pd.read_csv(
            fn, delimiter="\t", converters={col: decimal.Decimal for col in columns}
        ).rename(columns=columns).sort_values("fEnergyEV")
    # if idx == 1:
    #     break

assert set(dataframes) == included_materials


lut_source, test_source = tc3tg.generate_lookup_table_source(
    fb_name="FB_ScatteringFactorLUT",
    dataframes=dataframes,
    table_prefix="fTable_",
    lookup_input="fEnergyEV",
    use_var_const=False,
)

with open("FB_ScatteringFactorLUT.TcPOU", "wt") as fp:
    print(lut_source, file=fp)

with open("FB_ScatteringFactorLUT_Test.TcPOU", "wt") as fp:
    print(test_source, file=fp)
