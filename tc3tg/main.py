"""Create Beckhoff TwinCAT PLC source code from a dataframe."""
import dataclasses
import logging
import pathlib
import uuid

import hashlib
import jinja2
import numpy as np
import pandas as pd

from typing import Any, Dict, List, Tuple, Optional

logger = logging.getLogger(__name__)


MODULE_PATH = pathlib.Path(__file__).resolve().parent
LUT_CONST_TEMPLATE = MODULE_PATH / "templates" / "plc" / "table.TcPOU"
LUT_TEMPLATE = MODULE_PATH / "templates" / "plc" / "table-init.TcPOU"
CONSTANT_GVL_TEMPLATE = MODULE_PATH / "templates" / "plc" / "constants.TcGVL"
CONSTANT_GVL_LOOKUP_TEMPLATE = MODULE_PATH / "templates" / "plc" / "constants-lookup.TcPOU"
TEST_TEMPLATE = MODULE_PATH / "templates" / "plc" / "tests.TcPOU"


@dataclasses.dataclass
class Constant:
    name: str
    description: str
    value: float
    units: str
    uncertainty: Optional[float] = None
    caveat: Optional[str] = None
    key: Optional[str] = None


def df_data_to_var_code(df: pd.DataFrame) -> str:
    """
    Convert dataframe data to something insertable into the TcPOU VAR block.
    """
    return "\n    ".join(
        ", ".join(str(value) for value in tuple(row)) + ","
        for idx, (_, row) in enumerate(df.iterrows())
    ).rstrip(",")


def df_data_to_code(table_name: str, df: pd.DataFrame) -> str:
    """
    Convert dataframe data to something insertable into the implementation
    block.
    """
    rows = []

    for row_idx, (_, row) in enumerate(df.iterrows()):
        rows.append(
            " ".join(
                f"{table_name}[{row_idx}, {col_idx}] := {value};"
                for col_idx, value in enumerate(row)
            )
        )

    return "\n".join(rows)


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


def guid_from_string(name):
    """Get a deterministic GUID from a string that should be unique."""
    # Sorry, we only have 16 bytes in our UUIDs...
    hashed = hashlib.md5(name.encode("utf-8")).digest()
    logger.debug(
        "Generating UUID from string: %s -> %s", name, hashed
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
    lookup_index: int = 0,
) -> List[Dict[str, Any]]:
    """
    Take the dataframes dictionary and add on some useful things for the
    jinja template.
    """
    column_sets = set(tuple(df.columns) for df in dataframes.values())
    if len(column_sets) != 1:
        raise ValueError(
            f"Columns are not consistent between all tables: {column_sets}"
        )
    for name, df in dataframes.items():
        lookup_values = tuple(df[df.columns[lookup_index]])
        if tuple(sorted(lookup_values)) != lookup_values:
            raise ValueError(
                f"Table {name} column {lookup_index} is not sorted"
            )

        if len(set(lookup_values)) != len(lookup_values):
            raise ValueError(
                f"Table {name} column {lookup_index} has repeated entries"
            )

    return [
        dict(
            name=table_prefix + name,
            identifier=name,
            indices_string=f"0..{len(df) - 1}, 0..{len(df.columns) - 1}",
            bounds=(len(df) - 1, len(df.columns) - 1),
            first_lookup=float(df.iloc[0, 0]),
            last_lookup=float(df.iloc[-1, 0]),
            df=df,
            data_as_var_code=df_data_to_var_code(df),
            data_as_code=df_data_to_code(table_prefix + name, df),
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
    use_var_const: bool = False,
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

    use_var_const : bool, optional
        Store data in a VAR CONSTANT section.  Setting this to True will bloat
        the .tmc file proportional to the size of the tables supplied.  In the
        case of the CXRO database, this can be on the order of megabytes.  The
        alternative is to initialize the table on the FB initialization, which
        is the default.

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
        tables=_dataframes_to_template_list(table_prefix, dataframes,
                                            lookup_index=lookup_index),
        pou_guid=guid or guid_from_table(fb_name, dataframes),
        outputs=sample_df.columns[1:],
        data_type=data_type,
        lookup_input=lookup_input,
        lookup_index=lookup_index,
        row_delta=row_delta_variable or (lookup_input + "_RowDelta"),
    )
    template_fn = LUT_CONST_TEMPLATE if use_var_const else LUT_TEMPLATE
    template = jinja2.Template(open(template_fn, "rt").read())
    code = template.render(template_kw)

    template = jinja2.Template(open(TEST_TEMPLATE, "rt").read())
    test_fb_name = test_fb_name or f"{fb_name}_Test"
    template_kw.update(
        test_fb_name=test_fb_name,
        pou_guid=guid_from_table(test_fb_name, dataframes),
    )
    test_code = template.render(template_kw)
    return code, test_code


def generate_constant_table(
    name: str,
    constants: List[Constant],
    *,
    data_type: str = "LREAL",
    guid: str = "",
    lookup_by_key: bool = False,
    **kwargs
) -> Tuple[str, str]:
    """
    Generate a GVL constant table, with no interpolation.

    Parameters
    ----------
    name : str
        The code block name.

    constants : list of Constant
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

    **kwargs :
        Additional keyword arguments to pass to or override in the template.

    Returns
    -------
    code : str
        The constant table source code.
    """
    template_kw = dict(
        name=name,
        guid=guid or guid_from_string(name),
        data_type=data_type,
        constants=constants,
    )

    template_kw.update(kwargs)

    template_fn = (
        CONSTANT_GVL_LOOKUP_TEMPLATE
        if lookup_by_key 
        else CONSTANT_GVL_TEMPLATE 
    )
    template = jinja2.Template(open(template_fn, "rt").read())
    return template.render(template_kw)
