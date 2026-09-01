import pandas as pd
from copy import deepcopy


def convert_dbdate_to_datetime(df: pd.DataFrame) -> pd.DataFrame:
    """Convert columns with dbdate type to datetime columns"""

    # Copy
    tmp = deepcopy(df)

    cols = tmp.select_dtypes(include=["dbdate"]).columns
    for col in cols:
        tmp[col] = pd.to_datetime(tmp[col], errors="coerce")

    return tmp
