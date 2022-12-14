from typing import Dict
from typing import Optional

import numpy as np
import pandas as pd
from tqdm import tqdm

from tabata import Opset


def extract_consecutive_sequences(
    serie: pd.Series, minimum_duration: Optional[int] = None
) -> pd.DataFrame:
    """Computes the sequences of consecutive values in the serie.

    Args:
        serie (pd.Series): serie of consecutive values
        minimum_duration (Optional[int]): if specified, it only returns the consecutive sequences of duration
        larger than `minimum_duration`.

    Returns:
        pd.DataFrame: DataFrame describing the consecutive values
            * the columns of the returned DataFrame are:
                * `beginning`: index of the beginning of the sequence
                * `ending`: index of the ending of the sequence
                * `length`: length of the current consecutive sequence
                * `output_col`: value of the sequence

    Example:
        For instance, let a serie:
        ```
        | index |  |
        |---|---|
        | 1 | 0 |
        | 2 | 0 |
        | 3 | 2 |
        | 4 | 1 |
        | 5 | 1 |
        | 6 | 0 |
        ```

        Then, the function `extract_consecutive_sequences(serie)` will return
        ```
        | index | beginning | ending | output_col | length |
        |---:|---:|---:|---:|---:|
        | 0 | 0 | 1 | 0 | 2 |
        | 1 | 2 | 2 | 2 | 1 |
        | 2 | 3 | 4 | 1 | 2 |
        | 3 | 5 | 5 | 0 | 1 |
        ```
    """
    df = serie.to_frame("output_col")
    df["timestamp"] = df.index
    groupby_sequences = df.groupby(
        (df["output_col"] != df["output_col"].shift()).astype(int).cumsum()
    )
    sequences = groupby_sequences.agg(
        beginning=("timestamp", "min"),
        ending=("timestamp", "max"),
        output_col=("output_col", "max"),
    ).reset_index(drop=True)
    sequences["length"] = sequences["ending"] - sequences["beginning"] + 1

    if minimum_duration is not None:
        whitelisted_sequences = sequences[sequences["length"] > minimum_duration]
        whitelisted_sequences["ending"] = whitelisted_sequences.shift(-1)["beginning"]
        whitelisted_sequences["ending"].iloc[-1] = len(serie)
        whitelisted_sequences["ending"] = whitelisted_sequences["ending"].astype(int)
        return whitelisted_sequences
    return sequences


def clean_on_mode(serie: pd.Series, rolling_window: int = 300) -> pd.Series:
    """Clean a serie by blacklisting high frequencies.
    To do so, it computes a rolling windows of size `rolling_window` and computes the mode on each window.
    The centered value of a rolling window has the mode value of that rolling window.

    Args:
        serie (pd.Series): serie to clean
        rolling_window (int, optional): size of the rolling window. Defaults to 300.

    Returns:
        pd.Series: cleaned serie
    """
    df = serie.to_frame("output_col")
    df["output_col_temp"] = df["output_col"].copy()
    df["output_col"] = (
        df["output_col_temp"]
        .rolling(rolling_window, center=True)
        .apply(lambda x: int(x.mode()[0]))
    )
    df["output_col"].iloc[:rolling_window] = df["output_col_temp"].iloc[:rolling_window]
    df["output_col"].iloc[-rolling_window:] = df["output_col_temp"].iloc[
        -rolling_window:
    ]
    df["output_col"] = df["output_col"].astype(int)
    return df["output_col"]


def clean_on_length(serie: pd.Series, minimum_duration: int = 2 * 60) -> pd.Series:
    """Clean a serie by blacklisting high frequencies.
    To do so, it deletes the equal consecutive sequences of length inferior to `minimum_duration`.
    This function is much faster than `clean_on_mode`.
    Args:
        serie (pd.Series): serie to clean
        minimum_duration (int, optional): maximum size of the sequence to delete. Defaults to 2*60 (= 60min).
    Returns:
        pd.Series: cleaned serie
    Example:
        For instance, let a serie:
        ```
        | index |  |
        |---|---|
        | 1 | 0 |
        | 2 | 0 |
        | 3 | 2 |
        | 4 | 1 |
        | 5 | 1 |
        | 6 | 0 |
        ```
        Then, `clean_on_length(serie, minimum_duration=2)` will return
        ```
        | index |  |
        |---|---|
        | 1 | 0 |
        | 2 | 0 |
        | 3 | 0 |
        | 4 | 1 |
        | 5 | 1 |
        | 6 | 1 |
        ```
    """
    serie = serie.copy()

    def update_df_cl(row):
        serie.iloc[row["beginning"] : row["ending"]] = row["output_col"]
        return row

    sequences = extract_consecutive_sequences(serie, minimum_duration=minimum_duration)
    sequences.apply(update_df_cl, axis=1)
    return serie


def compute_attempted_sequence(
    df: pd.DataFrame,
    true_value: int = 1,
    minimum_distance: int = 2,
    minimum_duration: int = 20,
    output_column: str = "CL",
) -> pd.DataFrame:
    """
    Computes the sequences of continuous values in `df[output_column] == true_value`.

    Args:
        df (pd.DataFrame): DataFrame to inspect
        true_value (int): value of the cluster in `df[output_column]` to extract sequences from. Defaults to 1.
        minimum_distance (int): minimum distance between 2 continuous sequences in `df[output_column] == true_value` to be considered different sequence. Defaults to 2.
        minimum_duration (int): minimum duration of a sequence in `df[output_column] == true_value` to be considered. Defaults to 20.
        output_column (str): column containing the clustering predictions. Defaults to "CL"

    Returns:
        pd.DataFrame: Dataframe where each row represents a sequence of continuous values in the DataFrame `df[output_column]`
    """
    whitelisted_sequences = extract_consecutive_sequences(
        df[output_column], minimum_duration=minimum_duration
    )
    sequences = whitelisted_sequences[whitelisted_sequences["output_col"] == true_value]
    sequences["distance"] = (
        sequences["beginning"].shift(-1) - sequences["ending"]
    ).fillna(np.inf)

    return sequences[sequences["distance"] >= minimum_distance]


def check_aborted_landings(
    ds: Opset,
    minimum_distance: int = 2,
    minimum_duration: int = 20,
    output_column: str = "CL",
) -> Dict[str, np.ndarray]:
    """
    Compute the aborted landings in a dataset

    Args:
        ds (Opset): dataset of the flights
        minimum_distance (int): minimum distance between 2 continuous sequences in `df[output_column] == true_value` to be considered different sequence. Defaults to 2.
        minimum_duration (int): minimum duration of a sequence in `df[output_column] == true_value` to be considered. Defaults to 20.
        output_column (str): column containing the clustering predictions. Defaults to "CL"


    Returns:
        Dict[str, np.ndarray]: dict mapping:
            record_name -> [list of starting index of aborted landings]
    """
    ds.rewind()
    true_value = ds.df["CL"].iloc[1200]
    sequences = {}
    for df in tqdm(ds):
        current_sequences = compute_attempted_sequence(
            df, true_value, minimum_distance, minimum_duration, output_column
        )
        if len(current_sequences) > 1:
            sequences[df.index.name] = current_sequences["beginning"].values
    return sequences
