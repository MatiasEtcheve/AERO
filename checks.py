from functools import partial
from typing import List

import pandas as pd
from tables import NoSuchNodeError
from tqdm import tqdm

from tabata import Opset


def iteration_check(ds: Opset) -> List:
    """Does a shape check on Opset by iterating over it. Some records can't be iterated over (???).

    Args:
        ds (Opset): ds to check

    Returns:
        List: list of indices of problematic records in `ds.records`
    """
    problematic_sigpos = []
    progress_bar = tqdm(total=len(ds))
    ds.rewind()
    while ds.sigpos < len(ds):
        try:
            for df in ds[ds.sigpos :]:
                progress_bar.update(1)
        except NoSuchNodeError as e:
            problematic_sigpos.append(df.records[ds.sigpos])
            ds.sigpos += 1
            progress_bar.update(1)
        else:
            ds.sigpos = len(ds)
    progress_bar.close()
    return problematic_sigpos


def timeframe_check(df: pd.DataFrame, error: str = "silence") -> bool:
    """Checks if the index of a DataFrame is continuous

    Args:
        df (pd.DataFrame): DataFrame to check
        error (str, optional): Behaviour to do if the check is not verified. Cann be
            * `raise`: not passing the check will raise a `ValueError`
            * `silence: not `passing the check will return a `False`
        Defaults to "silence".

    Raises:
        ValueError: if the check is not passed and `error="raise`

    Returns:
        bool: whether the check passed on the current DataFrame
    """
    if not (df.index == list(range(len(df)))).all():
        message = f"The index on record {df.index.name} is not continuous"
        if error == "raise":
            raise ValueError(message)
        return False
    return True


def nan_check(df: pd.DataFrame, error="raise") -> bool:
    """Checks if the DataFrame contains any nan values. It doesn't fill the nan values if there are some.

    Args:
        df (pd.DataFrame): DataFrame to check
        error (str, optional): Behaviour to do if the check is not verified. Cann be
            * `raise`: not passing the check will raise a `ValueError`
            * `silence: not `passing the check will return a `False`
        Defaults to "silence".

    Raises:
        ValueError: if the check is not passed and `error="raise`

    Returns:
        bool: whether the check passed on the current DataFrame
    """
    if df.isna().sum().sum() > 0:
        message = f"The data on record {df.index.name} has nan values"
        if error == "raise":
            raise ValueError(message)
        return False
    return True


def column_check(
    df: pd.DataFrame, required_columns: List[str], error="silence"
) -> bool:
    """Checks if the DataFrame contains the `required_column`.

    Args:
        df (pd.DataFrame): DataFrame to check
        required_columns (List[str]): list of required columns in the DataFrame
        error (str, optional): Behaviour to do if the check is not verified. Cann be
            * `raise`: not passing the check will raise a `ValueError`
            * `silence: not `passing the check will return a `False`
        Defaults to "silence".

    Raises:
        ValueError: if the check is not passed and `error="raise`

    Returns:
        bool: whether the check passed on the current DataFrame
    """
    if set(df.columns) != set(required_columns):
        message = f"The data on record {df.index.name} has not the required columns."
        if error == "raise":
            raise ValueError(message)
        return False
    return True


def duration_check(df: pd.DataFrame, error="raise") -> bool:
    """Checks if the DataFrame is long enough (at least 2 000s = 33min) or the max altitude is high enough (at least 2 000ft = 610m).

    Args:
        df (pd.DataFrame): DataFrame to check
        error (str, optional): Behaviour to do if the check is not verified. Cann be
            * `raise`: not passing the check will raise a `ValueError`
            * `silence: not `passing the check will return a `False`
        Defaults to "silence".

    Raises:
        ValueError: if the check is not passed and `error="raise`

    Returns:
        bool: whether the check passed on the current DataFrame
    """
    if df["ALT [ft]"].max() < 2000 or df.index.max() < 2000:
        message = f"There is not flight on record {df.index.name}."
        if error == "raise":
            raise ValueError(message)
        return False
    return True


def health_check(ds: Opset):
    """Does a complete health check on the DataFrames of the dataset `ds`. This health check is composed of
        * iteration check: some dataframe in the dataset can't be iterated over
        * timeframe check: check if the DataFrame index are continuous
        * nan check: check if the DataFrame contains any nan values
        * column check: check if all the DataFrames contain the columns of the first DataFrame (which is supposed to be healthy)
        * duration check: check if the DataFrame is long enough

    Args:
        ds (Opset): dataset to check

    Returns:
        Dict[Callable, List[str]]: dictionnary whose:
            * keys are the checks (as Callable)
            * values are the list of record names of DataFrames in the dataset which didn't passed the check
    """
    required_columns = ds[0].columns
    checks = [
        timeframe_check,
        nan_check,
        partial(column_check, required_columns=required_columns),
        duration_check,
    ]
    print("Checking if every dataframe is iterable...")
    non_iterable_df = iteration_check(ds)
    [ds.records.pop(index) for index in sorted(non_iterable_df, reverse=True)]

    print("Health checks: continuous, duration, components...")
    problematic_records = {str(check): [] for check in checks}
    ds.rewind()
    for df in tqdm(ds):
        for check in checks:
            try:
                check(df)
            except (ValueError, KeyError):
                problematic_records[str(check)].append(df.index.name)
    ds.rewind()
    return problematic_records


def remove_problematic_records(ds: Opset):
    """Performs a health check on the dataset

    Args:
        ds (Opset): dataset composed of DataFrames to check
    """
    dict_problematic_records = health_check(ds)
    set_problematic_records = set(sum(dict_problematic_records.values(), []))
    for problematic_record in set_problematic_records:
        ds.records.remove("/" + problematic_record)

if __name__ == "main":
    print("maqueu")
