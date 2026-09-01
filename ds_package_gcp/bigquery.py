from google.cloud import bigquery
import pandas as pd
import time
from jinja2 import Environment
from pathlib import Path
from importlib import resources
from datetime import datetime
import warnings

from ds_package_gcp.utils import convert_dbdate_to_datetime


class DataLoader:
    """
    Class for all bigquery tasks

    __ PARAMETERS __
    :project: str
        The project name in which the bigquery client will be created.
    :location: str
        The location of the bigquery client.
    """

    def __init__(self, project: str = "sf-da-dwh", location: str = "europe-west3"):

        # Init bigquery
        self.client = bigquery.Client(project=project, location=location)

    def run_query(self, query: str) -> pd.DataFrame:
        """
        Executes a SQL query using the client connection and returns the results as a pandas DataFrame.

        __ PARAMETERS __
        query: str
            SQL query string to be executed.

        __ RETURNS __
        pd.DataFrame
            DataFrame containing the query results, with dbdate columns converted to datetime format.
        """

        # Run the query
        query_job = self.client.query(query)

        # Convert the results to a DataFrame
        results = query_job.to_dataframe()

        # Convert columns with dbdate type to datetime columns
        results = convert_dbdate_to_datetime(results)

        return results

    def download_dataset(self, dataset_name: str, table_name: str) -> pd.DataFrame:
        """
        Loads a table from the specified dataset and returns its contents as a pandas DataFrame.

        __ PARAMETERS __
        dataset_name: str
            Name of the dataset containing the table.
        table_name: str
            Name of the table to be loaded.

        __ RETURNS __
        pd.DataFrame
            DataFrame containing all rows from the specified table, with dbdate columns converted to datetime format.
        """

        # Query
        query = f"SELECT * FROM {dataset_name}.{table_name}"

        # Load the table
        table = self.client.query(query).to_dataframe()

        # Convert columns with dbdate type to datetime columns
        table = convert_dbdate_to_datetime(table)

        return table

    def append_table(
        self,
        dataset_name: str,
        table_name: str,
        table: pd.DataFrame,
        session_id: str = None,
    ):
        """
        Appends a pandas DataFrame to a BigQuery table, creating the table automatically if it does not exist.

        __ PARAMETERS __
        dataset_name: str
            Name of the dataset containing the target table.
        table_name: str
            Name of the table to append data to.
        table: pd.DataFrame
            DataFrame containing the rows to be appended.
        session_id: str
            Optional session identifier to be added as a column to all rows before upload.

        __ RETURNS __
        None
            This function does not return a value. It completes when the append job succeeds or raises an exception after maximum retries.
        """

        # Add session_id if provided
        if session_id is not None:
            table["session_id"] = session_id

        # Convert datetime columns to date
        cols = table.select_dtypes(include=["datetime"]).columns
        for col in cols:
            table[col] = table[col].dt.date

        # Specify the table ID
        table_id = f"{dataset_name}.{table_name}"

        # Create a LoadJobConfig to specify the write disposition
        job_config = bigquery.LoadJobConfig(
            write_disposition=bigquery.WriteDisposition.WRITE_APPEND,
            autodetect=True,  # Makes job create a table if one doesn't already exist
        )

        # Create the job
        job = self.client.load_table_from_dataframe(
            table, table_id, job_config=job_config
        )

        # Safely run the append job - 5 tries
        attempt = 0
        while attempt <= 5:
            try:
                job.result()  # Wait for the job to complete
                if job.errors:
                    # Check for rateLimitExceeded
                    if any(
                        "rateLimitExceeded" in e.get("message", "") for e in job.errors
                    ):
                        wait_time = 5 * (2**attempt)  # Exponential wait time
                        print(
                            f"Rate limit exceeded, retrying in {wait_time:.2f} seconds..."
                        )
                        time.sleep(wait_time)
                        attempt += 1
                    else:
                        print("Non-retryable errors encountered:", job.errors)
                        raise Exception(job.errors)
                else:
                    print("Append successful")
                    return
            except Exception as e:
                # In some cases, job.result() itself raises, we want to retry only if it's rate-limiting
                if "rateLimitExceeded" in str(e):
                    wait_time = 5 * (2**attempt)
                    print(
                        f"Rate limit (via exception), retrying in {wait_time:.2f} seconds..."
                    )
                    time.sleep(wait_time)
                    attempt += 1
                else:
                    print("Non-retryable exception:", e)
                    raise

        raise Exception("Max retries exceeded")

    def overwrite_table(
        self,
        dataset_name: str,
        table_name: str,
        table: pd.DataFrame,
        session_id: str = None,
        add_timestamp: bool = False,
    ):
        """
        Overwrites a BigQuery table with the contents of a pandas DataFrame.

        __ PARAMETERS __
        dataset_name: str
            Name of the dataset containing the target table.
        table_name: str
            Name of the table to be overwritten.
        table: pd.DataFrame
            DataFrame containing the data to upload.
        session_id: str
            Optional session identifier to be added as a column to all rows before upload.
        add_timestamp: bool
            If True, adds a created_at timestamp column with the current UTC time.
        """

        # Convert datetime columns to date
        cols = table.select_dtypes(include=["datetime"]).columns
        for col in cols:
            table[col] = table[col].dt.date

        # Add a timestamp if required
        if add_timestamp is True:
            table["created_at"] = pd.Timestamp.utcnow().tz_localize(None)

        # Add session_id if provided
        if session_id is not None:
            table["session_id"] = session_id

        # Specify the table ID
        table_id = f"{dataset_name}.{table_name}"

        # Create a LoadJobConfig to specify the write disposition
        job_config = bigquery.LoadJobConfig(
            write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE
        )

        # Load the DataFrame to BigQuery, overwriting the table
        job = self.client.load_table_from_dataframe(
            table, table_id, job_config=job_config
        )

        # Wait for the job to complete
        job.result()

    def overwrite_table_from_query(
        self, dataset_name: str, table_name: str, query: str
    ):
        """
        Overwrites a BigQuery table using the result of a SQL query.

        __ PARAMETERS __
        dataset_name: str
            Name of the dataset containing the target table.
        table_name: str
            Name of the table to be overwritten.
        query: str
            SQL query whose result will be used to replace the contents of the target table.
        """

        # Specify the destination table ID
        table_id = f"{self.client.project}.{dataset_name}.{table_name}"

        # Create a QueryJobConfig to specify the write disposition
        job_config = bigquery.QueryJobConfig(
            destination=table_id,
            write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
        )

        # Start the query, passing in the extra configuration.
        query_job = self.client.query(query, job_config=job_config)

        # Wait for the job to complete.
        query_job.result()

    def create_table(self, dataset_name: str, table_name: str):
        """
        Creates an empty table in BigQuery.

        __ PARAMETERS __
        dataset_name: str
            Name of the dataset where the table will be created.
        table_name: str
            Name of the table to be created.

        __ RETURNS __
        google.cloud.bigquery.table.Table
            The created BigQuery table object.
        """

        # Specify the table ID
        table_id = f"{dataset_name}.{table_name}"

        # Create a table
        table = self.client.create_table(table_id)

        return table

    def delete_table(self, dataset_name: str, table_name: str):
        """
        Deletes a table from BigQuery.

        __ PARAMETERS __
        dataset_name: str
            Name of the dataset containing the table.
        table_name: str
            Name of the table to be deleted.
        """

        # Specify the table ID
        table_id = f"{dataset_name}.{table_name}"

        # Delete the table
        self.client.delete_table(table_id)

    def replace_partition(
        self,
        dataset_name: str,
        table_name: str,
        partition_name: str,
        table: pd.DataFrame,
    ):
        """
        Overwrites a specific partition of a BigQuery table with new data.

        __ PARAMETERS __
        dataset_name: str
            Name of the dataset containing the target table.
        table_name: str
            Name of the partitioned table.
        partition_name: str
            Identifier of the partition to be replaced.
        table: pd.DataFrame
            DataFrame containing the data that will overwrite the specified partition.
        """

        # Rewrite the table_name with the partition
        table_name_with_partition = f"{table_name}${partition_name}"

        # Call the overwrite_table method
        self.overwrite_table(
            dataset_name=dataset_name,
            table_name=table_name_with_partition,
            table=table,
        )

    def run_query_from_template(self, root_package: str, template_path: str, **kwargs):
        """
        Executes a BigQuery SQL query rendered from a Jinja template and returns the result as a pandas DataFrame.

        __ PARAMETERS __
        root_package: str
            Root package path used to locate the SQL template file.
        template_path: str
            Relative path to the Jinja SQL template file.
        **kwargs
            Key-value pairs used to render variables inside the Jinja template.

        __ RETURNS __
        pd.DataFrame
            DataFrame containing the results of the executed SQL query.
        """
        # Real path
        real_path = self._get_sql_path(root_package, template_path)

        # Read the template content
        template_str = Path(real_path).read_text()

        # Create environment
        jinja_env = Environment()

        # Load template from string
        template = jinja_env.from_string(template_str)

        # Render the SQL template with the provided parameter
        sql_query = template.render(**kwargs)

        # Execute the query
        query_job = self.client.query(sql_query)

        return convert_dbdate_to_datetime(query_job.result().to_dataframe())

    def _get_sql_path(self, root_package: str, file_path: str) -> str:
        """
        Resolves the absolute file system path of a SQL template file stored within a Python package.

        __ PARAMETERS __
        root_package: str
            Root Python package where SQL templates are stored.
        file_path: str
            Relative path to the SQL file within the package.

        __ RETURNS __
        str
            Absolute file system path to the resolved SQL file.

        __ RAISES __
        FileNotFoundError
            If the specified SQL file does not exist within the package.
        """

        sql_file = resources.files(root_package).joinpath(file_path)

        if not sql_file.exists():
            raise FileNotFoundError(f"SQL file not found: {file_path}")

        return str(sql_file)

    def replace_partition_from_query(
        self,
        source_dataset: str,
        source_table: str,
        destination_dataset: str,
        destination_table: str,
        partition_name: str,
        partition_column: str,
        partition_is_a_date: bool = True,
    ):
        """
        Replace a single partition of destination_dataset.destination_table with the rows of
        source_dataset.source_table, tagging each row with partition_name in
        partition_column. Runs entirely in BigQuery via a query job with a
        partition-decorator destination and WRITE_TRUNCATE disposition.

        The destination table must already exist and be partitioned by
        partition_column.

        __ PARAMETERS __
        source_dataset: str
            The dataset of the source data
        source_table: str
            The source data
        destination_dataset: str
            The destination dataset
        destination_table: str
            The destination table
        partition_name: str
            The name of the partition
        partition_column: str
            The column of partition
        partition_is_a_date: bool
            Convert partition name to date in BigQuery
        """

        # Ensure the base query doesn't include the partition_column
        # If it exists it will be replaced
        table_id = f"{source_dataset}.{source_table}"
        cols = {f.name for f in self.client.get_table(table_id).schema}
        if partition_column in cols:
            warnings.warn(
                f"{table_id}: existing {partition_column} column will be replaced"
            )
            base_query = f"SELECT * EXCEPT({partition_column}) FROM `{table_id}`"
        else:
            base_query = f"SELECT * FROM `{table_id}`"

        if partition_is_a_date:

            # Validate partition_name format when it's a date
            try:
                datetime.strptime(partition_name, "%Y-%m-%d")
            except ValueError as e:
                raise ValueError(
                    f"partition_name must be in YYYY-MM-DD format when "
                    f"partition_is_a_date=True, got {partition_name!r}"
                ) from e

            # Create destination and query
            destination = (
                f"{self.client.project}.{destination_dataset}.{destination_table}"
                f"${partition_name.replace('-','')}"
            )
            query = (
                f"SELECT *, DATE('{partition_name}') AS {partition_column} "
                f"FROM ({base_query})"
            )

        else:
            # Create destination and query
            destination = (
                f"{self.client.project}.{destination_dataset}.{destination_table}"
                f"${partition_name}"
            )
            query = (
                f"SELECT *, {partition_name} AS {partition_column} "
                f"FROM ({base_query})"
            )

        # Config
        job_config = bigquery.QueryJobConfig(
            destination=destination,
            write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
        )

        # Replace
        self.client.query(query, job_config=job_config).result()
