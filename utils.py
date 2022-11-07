import pandas as pd


def compute_consecutive_sequences(serie: pd.Series) -> pd.DataFrame:
    """Computes the sequences of consecutive values in the serie.

    Args:
        serie (pd.Series): serie of consecutive values

    Returns:
        pd.DataFrame: DataFrame describing the consecutive values
            * the columns of the returned DataFrame are:
                * `beginning`: index of the beginning of the sequence
                * `ending`: index of the ending of the sequence
                * `length`: length of the current consecutive sequence
                * `output_col`: value of the sequence

    Example:
        For instance, let a DataFrame:
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

        Then, this function will return
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
    return sequences
