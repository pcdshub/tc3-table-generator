"""Create Beckhoff TwinCAT PLC source code from a dataframe."""
import sys
import jinja2
import uuid
import logging

import pathlib
import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")  # noqa

import matplotlib.pyplot as plt  # noqa

logger = logging.getLogger(__name__)


# PLC file output settings:
MODULE_PATH = pathlib.Path(__file__).resolve().parent

pd.set_option("display.max_rows", 1000)


def df_data_to_code(df):
    return "\n    ".join(
        ", ".join(
            str(value)
            for attr, value in dict(row).items()
        ) + ","
        for idx, (_, row) in enumerate(df.iterrows())
    ).rstrip(",")


def guid_from_table(fb_name, dfs):
    """
    Get a deterministic GUID from some key items.

    This may not be perfect, so let's choose our FB names wisely.
    """
    total_rows = sum(len(df) for df in dfs.values())
    maybe_unique = (fb_name + list(dfs)[0] + str(total_rows)) * 2
    logger.debug("Generating UUID from string: %s -> %s", maybe_unique, maybe_unique[:16])
    return uuid.UUID(bytes=maybe_unique.encode("utf-8")[:16])


def generate_lookup_table_source(
    fb_name,
    dataframes,
    data_type="LREAL",
    guid=None,
    table_prefix="fTable_",
    lookup_input="fLookup",
    row_delta_variable="",
):
    """
    Generate a string-keyed set of lookup tables, where output values are
    interpolated between rows.

    Limitations:

    * No beyond-table value interpolation is performed
    * The index must be the first column
    * All dataframes must have the same set of columns
    * All data must be of a consistent data type; i.e., the passed
      in``data_type``
    """
    tables = []

    sample_df = list(dataframes.values())[0]
    assert len(set(tuple(df.columns) for df in dataframes.values())) == 1

    # index_col = list(sample_df.columns).index(index)

    for name, df in dataframes.items():
        tables.append(
            dict(
                name=table_prefix + name,
                identifier=name,
                indices_string=f"0..{len(df) - 1}, 0..{len(df.columns) - 1}",
                bounds=(len(df) - 1, len(df.columns) - 1),
                last_lookup=df.iloc[-1, 0],
                df=df,
                data_as_code=df_data_to_code(df),
                data_type=data_type,
            )
        )

    template = jinja2.Template(
        open(MODULE_PATH / "templates" / "plc" / "table.TcPOU", "rt").read()
    )
    return template.render(
        fb_name=fb_name,
        tables=tables,
        pou_guid=guid or guid_from_table(fb_name, dataframes),
        outputs=sample_df.columns[1:],
        data_type=data_type,
        lookup_input=lookup_input,
        row_delta=row_delta_variable or (lookup_input + "_RowDelta"),
    )
