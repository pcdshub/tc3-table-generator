"""Create Beckhoff TwinCAT PLC source code from a dataframe."""
import logging
import pathlib
import uuid

import hashlib
import jinja2
import numpy as np
import pandas as pd

from typing import Any, Dict, List, Tuple

logger = logging.getLogger(__name__)


# PLC file output settings:
MODULE_PATH = pathlib.Path(__file__).resolve().parent
LUT_TEMPLATE = MODULE_PATH / "templates" / "plc" / "table.TcPOU"
TEST_TEMPLATE = MODULE_PATH / "templates" / "plc" / "tests.TcPOU"


def df_data_to_code(df):
    """
    Convert dataframe data to something insertable into the TcPOU VAR block.
    """
    return "\n    ".join(
        ", ".join(str(value) for attr, value in dict(row).items()) + ","
        for idx, (_, row) in enumerate(df.iterrows())
    ).rstrip(",")


def guid_from_table(fb_name, dfs):
    """
    Get a deterministic GUID from some key items.

    This may not be perfect, so let's choose our FB names wisely.
    """
    total_rows = sum(len(df) for df in dfs.values())

    maybe_unique = fb_name + ",".join(list(dfs)) + str(total_rows)
    # Sorry, we only have 16 bytes in our UUIDs...
    hashed = hashlib.md5(maybe_unique.encode("utf-8")).digest()
    logger.debug(
        "Generating UUID from string: %s -> %s", maybe_unique, hashed
    )
    return uuid.UUID(bytes=hashed)


def generate_test_values(df: pd.DataFrame, count: int):
    # Pick some values that are in the table
    span_indices = range(1, len(df), len(df) // count)
    indices = [0] + list(span_indices) + [len(df) - 1]
    values = []
    for index in indices:
        values.append(
            dict(zip(df.columns, df.iloc[index, :]))
        )

    # Then some that are between rows - this thing should interpolate, after
    # all
    factor = 1
    for index in span_indices:
        row1 = df.astype(float).iloc[index - 1, :]
        row2 = df.astype(float).iloc[index, :]
        # Go inbetween the rows by some factor
        factor = (factor + 1) % 10 + 1

        slope = (row2 - row1) / (row2[0] - row1[0])
        lookup = row1[0] + (row2 - row1)[0] * (factor / 10.)
        item = row1 + slope * (lookup - row1[0])
        values.append(dict(zip(df.columns, item)))

    return values


def _dataframes_to_template_list(
    table_prefix: str,
    dataframes: Dict[str, pd.DataFrame],
    test_values: int = 10,
) -> List[Dict[str, Any]]:
    """
    Take the dataframes dictionary and add on some useful things for the
    jinja template.
    """
    assert len(set(tuple(df.columns) for df in dataframes.values())) == 1

    return [
        dict(
            name=table_prefix + name,
            identifier=name,
            indices_string=f"0..{len(df) - 1}, 0..{len(df.columns) - 1}",
            bounds=(len(df) - 1, len(df.columns) - 1),
            first_lookup=float(df.iloc[0, 0]),
            last_lookup=float(df.iloc[-1, 0]),
            df=df,
            data_as_code=df_data_to_code(df),
            test_values=generate_test_values(df, test_values),
        )
        for name, df in dataframes.items()
    ]


def generate_lookup_table_source(
    fb_name: str,
    dataframes: Dict[str, pd.DataFrame],
    *,
    data_type: str = "LREAL",
    guid: str = "",
    table_prefix: str = "fTable_",
    lookup_input: str = "fLookup",
    lookup_index: int = 0,
    row_delta_variable: str = "",
    test_fb_name: str = "",
) -> Tuple[str, str]:
    """
    Generate a string-keyed set of lookup tables, where output values are
    interpolated between rows.

    Limitations:

    * No beyond-table value interpolation is performed
    * The index must be the first column
    * All dataframes must have the same set of columns
    * All data must be of a consistent data type; i.e., the passed
      in``data_type``

    Parameters
    ----------
    fb_name : str
        The function block name.

    dataframes : Dict[str, pandas.DataFrame]
        Dictionary of name to dataframe.

    data_type : str, optional
        The data type. Defaults to LREAL.

    guid : str, optional
        The function block globally unique identifier / GUID.

    table_prefix : str, optional
        The name with which to prefix all table arrays.

    lookup_input : str, optional
        The function block input variable name - the indexed parameter which
        you're looking up in the table.

    lookup_index : int, optional
        The per-row array index of the lookup value.  Not fully supported
        just let; leave this at 0 for now.

    row_delta_variable : str, optional
        The auto-generated code delta variable.  Not necessary to set, unless
        you really want to customize the output.

    Returns
    -------
    code : str
        The lookup table source code.

    test_code : str
        The TcUnit-compatible test suite.
    """
    sample_df = list(dataframes.values())[0]
    template_kw = dict(
        fb_name=fb_name,
        tables=_dataframes_to_template_list(table_prefix, dataframes),
        pou_guid=guid or guid_from_table(fb_name, dataframes),
        outputs=sample_df.columns[1:],
        data_type=data_type,
        lookup_input=lookup_input,
        lookup_index=lookup_index,
        row_delta=row_delta_variable or (lookup_input + "_RowDelta"),
    )
    template = jinja2.Template(open(LUT_TEMPLATE, "rt").read())
    code = template.render(template_kw)

    template = jinja2.Template(open(TEST_TEMPLATE, "rt").read())
    test_fb_name = test_fb_name or f"{fb_name}_Test"
    template_kw.update(
        test_fb_name=test_fb_name,
        pou_guid=guid_from_table(test_fb_name, dataframes),
    )
    test_code = template.render(template_kw)
    return code, test_code
