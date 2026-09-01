import pandas as pd
import pytest

from ds_package_gcp.bigquery import DataLoader


def test_run_query():
    data_loader = DataLoader()

    query = """
    SELECT *
    FROM ds_test.test_run_query
    LIMIT 5
    """

    df_result = data_loader.run_query(query)

    # Type check
    assert isinstance(df_result, pd.DataFrame)

    # Not empty
    assert not df_result.empty

    # Expected columns
    expected_columns = {
        "test_date",
        "test_string",
        "test_int",
        "test_bool",
        "session_id",
    }
    assert set(df_result.columns) == expected_columns

    # Row count (based on your seeded test data)
    assert len(df_result) == 5


def test_append_table():
    data_loader = DataLoader()

    session_id = "test_append_table"

    # Clean table before test
    cleanup_query = f"""
    DELETE FROM ds_test.test_run_query
    WHERE session_id = '{session_id}'
    """
    data_loader.run_query(cleanup_query)

    # Create test dataframe to append
    df = pd.DataFrame(
        {
            "test_date": [pd.Timestamp("2026-01-01")],
            "test_string": ["pytest_append"],
            "test_int": [123],
            "test_bool": [True],
        }
    )

    # Run append (session_id as datetime, not string UUID)
    data_loader.append_table(
        dataset_name="ds_test",
        table_name="test_table_read",
        table=df,
        session_id=session_id,
    )

    # Query back only inserted row
    query = f"""
    SELECT *
    FROM ds_test.test_table_read
    WHERE session_id = '{session_id}'
    """

    result = data_loader.run_query(query)

    # Assertions
    assert isinstance(result, pd.DataFrame)
    assert len(result) == 1

    row = result.iloc[0]

    assert row["test_string"] == "pytest_append"
    assert row["test_int"] == 123
    assert row["test_bool"]

    # Clean table after test
    cleanup_query = f"""
    DELETE FROM ds_test.test_table_read
    WHERE session_id = '{session_id}'
    """
    data_loader.run_query(cleanup_query)


def test_overwrite_table():
    data_loader = DataLoader()

    table_name = "test_overwrite_table"
    session_id = "test_overwrite"

    # -----------------
    # First write
    # -----------------
    df1 = pd.DataFrame(
        {
            "test_string": ["row_1"],
            "test_int": [1],
            "test_bool": [True],
        }
    )

    data_loader.overwrite_table(
        dataset_name="ds_test",
        table_name=table_name,
        table=df1,
        session_id=session_id,
        add_timestamp=True,
    )

    # -----------------
    # Second write (should replace first)
    # -----------------
    df2 = pd.DataFrame(
        {
            "test_string": ["row_2"],
            "test_int": [999],
            "test_bool": [False],
        }
    )

    data_loader.overwrite_table(
        dataset_name="ds_test",
        table_name=table_name,
        table=df2,
        session_id=session_id,
        add_timestamp=True,
    )

    # -----------------
    # Query result
    # -----------------
    query = f"""
    SELECT *
    FROM ds_test.{table_name}
    """

    df_result = data_loader.run_query(query)

    # -----------------
    # Assertions
    # -----------------
    assert isinstance(df_result, pd.DataFrame)

    # Only second overwrite row should exist
    assert len(df_result) == 1

    row = df_result.iloc[0]

    assert row["test_string"] == "row_2"
    assert row["test_int"] == 999
    assert not bool(row["test_bool"])
    assert row["session_id"] == session_id

    # created_at exists and populated
    assert "created_at" in df_result.columns
    assert pd.notnull(row["created_at"])


def test_overwrite_table_from_query():
    data_loader = DataLoader()

    table_name = "test_overwrite_table_from_query"

    # First load some junk data into target table
    df = pd.DataFrame({"value": ["old_row"]})

    data_loader.overwrite_table(
        dataset_name="ds_test",
        table_name=table_name,
        table=df,
    )

    # Now overwrite via query
    query = """
    SELECT
        'new_row' AS value
    """

    data_loader.overwrite_table_from_query(
        dataset_name="ds_test",
        table_name=table_name,
        query=query,
    )

    # Validate
    result = data_loader.run_query(
        f"""
    SELECT *
    FROM ds_test.{table_name}
    """
    )

    assert isinstance(result, pd.DataFrame)
    assert len(result) == 1
    assert result.iloc[0]["value"] == "new_row"


def test_delete_table():
    data_loader = DataLoader()

    table_name = "test_delete_table"

    # Create table first
    data_loader.create_table(
        dataset_name="ds_test",
        table_name=table_name,
    )

    # Confirm it exists
    before = data_loader.run_query(
        f"""
    SELECT table_name
    FROM ds_test.INFORMATION_SCHEMA.TABLES
    WHERE table_name = '{table_name}'
    """
    )

    assert len(before) == 1

    # Delete it
    data_loader.delete_table(
        dataset_name="ds_test",
        table_name=table_name,
    )

    # Confirm deleted
    after = data_loader.run_query(
        f"""
    SELECT table_name
    FROM ds_test.INFORMATION_SCHEMA.TABLES
    WHERE table_name = '{table_name}'
    """
    )

    assert len(after) == 0


def test_replace_partition():
    data_loader = DataLoader()

    table_name = "test_replace_partition"

    # Create partitioned table manually
    data_loader.run_query(
        f"""
    CREATE OR REPLACE TABLE ds_test.{table_name}
    (
        test_date DATE,
        test_string STRING,
        test_int INT64
    )
    PARTITION BY test_date
    """
    )

    # Seed two partitions
    data_loader.run_query(
        f"""
    INSERT INTO ds_test.{table_name}
    VALUES
        ('2026-04-28', 'old_partition_data', 1),
        ('2026-04-29', 'other_partition_data', 2)
    """
    )

    # Replace partition 2026-04-28
    df = pd.DataFrame(
        {
            "test_date": [pd.Timestamp("2026-04-28")],
            "test_string": ["new_partition_data"],
            "test_int": [999],
        }
    )

    data_loader.replace_partition(
        dataset_name="ds_test",
        table_name=table_name,
        partition_name="20260428",
        table=df,
    )

    # Query all rows
    result = data_loader.run_query(
        f"""
    SELECT *
    FROM ds_test.{table_name}
    ORDER BY test_date
    """
    )

    assert len(result) == 2

    # Replaced partition
    row1 = result.iloc[0]
    assert str(row1["test_date"])[:10] == "2026-04-28"
    assert row1["test_string"] == "new_partition_data"
    assert row1["test_int"] == 999

    # Untouched partition
    row2 = result.iloc[1]
    assert str(row2["test_date"])[:10] == "2026-04-29"
    assert row2["test_string"] == "other_partition_data"
    assert row2["test_int"] == 2


def test_replace_partition_from_query():
    data_loader = DataLoader()

    source_table = "test_replace_partition_from_query_source"
    destination_table = "test_replace_partition_from_query_dest"

    # Create source table (no partition column - the function adds it)
    data_loader.run_query(
        f"""
    CREATE OR REPLACE TABLE ds_test.{source_table}
    (
        test_string STRING,
        test_int INT64
    )
    """
    )

    # Seed source with rows to copy into the replaced partition
    data_loader.run_query(
        f"""
    INSERT INTO ds_test.{source_table}
    VALUES
        ('new_partition_data', 999),
        ('new_partition_data_2', 1000)
    """
    )

    # Create partitioned destination table
    data_loader.run_query(
        f"""
    CREATE OR REPLACE TABLE ds_test.{destination_table}
    (
        test_string STRING,
        test_int INT64,
        test_date DATE
    )
    PARTITION BY test_date
    """
    )

    # Seed destination with two partitions
    data_loader.run_query(
        f"""
    INSERT INTO ds_test.{destination_table}
    VALUES
        ('old_partition_data', 1, '2026-04-28'),
        ('other_partition_data', 2, '2026-04-29')
    """
    )

    # Replace partition 2026-04-28 from the source query
    data_loader.replace_partition_from_query(
        source_dataset="ds_test",
        source_table=source_table,
        destination_dataset="ds_test",
        destination_table=destination_table,
        partition_name="2026-04-28",
        partition_column="test_date",
        partition_is_a_date=True,
    )

    # Query all rows
    result = data_loader.run_query(
        f"""
    SELECT *
    FROM ds_test.{destination_table}
    ORDER BY test_date, test_int
    """
    )

    # Two new rows in replaced partition + one untouched row
    assert len(result) == 3

    # Replaced partition - row 1
    row1 = result.iloc[0]
    assert str(row1["test_date"])[:10] == "2026-04-28"
    assert row1["test_string"] == "new_partition_data"
    assert row1["test_int"] == 999

    # Replaced partition - row 2
    row2 = result.iloc[1]
    assert str(row2["test_date"])[:10] == "2026-04-28"
    assert row2["test_string"] == "new_partition_data_2"
    assert row2["test_int"] == 1000

    # Untouched partition
    row3 = result.iloc[2]
    assert str(row3["test_date"])[:10] == "2026-04-29"
    assert row3["test_string"] == "other_partition_data"
    assert row3["test_int"] == 2


def test_replace_partition_from_query_invalid_date_format():
    data_loader = DataLoader()

    # Each of these should fail the YYYY-MM-DD validation
    invalid_partition_names = [
        "20260428",  # compact form, no dashes
        "2026/04/28",  # wrong separator
        "28-04-2026",  # DD-MM-YYYY
        "not-a-date",  # garbage
        "",  # empty
    ]

    for partition_name in invalid_partition_names:
        with pytest.raises(ValueError, match="YYYY-MM-DD"):
            data_loader.replace_partition_from_query(
                source_dataset="ds_test",
                source_table="test_replace_partition_from_query_source",
                destination_dataset="ds_test",
                destination_table="test_replace_partition_from_query_dest",
                partition_name=partition_name,
                partition_column="test_date",
                partition_is_a_date=True,
            )


def test_run_query_from_template():
    data_loader = DataLoader()

    result = data_loader.run_query_from_template(
        root_package="tests",
        template_path="sql/test_query_template.sql",
        value="pytest_template",
        number=123,
    )

    assert isinstance(result, pd.DataFrame)
    assert len(result) == 1

    row = result.iloc[0]

    assert row["test_string"] == "pytest_template"
    assert row["test_int"] == 123
