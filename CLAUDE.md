# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A Poetry-managed Python library of GCP helpers (BigQuery + Vertex AI) maintained by the Roadsurfer data science team. It is published as a wheel to a private GCP Artifact Registry repo (`ds-packages` in `europe-west3`) and consumed by other DS projects — it is a library, not an app, so there is no entrypoint to run.

## Common commands

Everything goes through the [Makefile](Makefile) (which wraps Poetry):

```bash
make install   # poetry install
make format    # black on ds_package_gcp + tests
make lint      # flake8 on ds_package_gcp + tests (config in .flake8)
make test      # pytest tests
make all       # install + format + lint + test (this is what CI runs)
make build     # poetry build (wheel)
```

Run a single test:

```bash
poetry run pytest tests/test_bigquery.py::test_replace_partition -v
```

CI (`.github/workflows/CI.yaml`) runs `make all` AND then `git diff --exit-code` — i.e. if `black` modifies any file, CI fails. Always run `make format` before committing.

## Branch & release flow

- Feature branches → PR into `main`. CI (`.github/workflows/CI.yaml`) runs on PRs targeting `main`.
- Push to `main` triggers `CD.yaml` (also runnable manually via `workflow_dispatch`): `poetry build` then `twine upload` to `https://europe-west3-python.pkg.dev/${GCP_PROJECT_ID}/ds-packages`. Bump `version` in [pyproject.toml](pyproject.toml) when shipping a release, or the upload will collide with an existing version.

## Tests hit real BigQuery

There is no mocking layer. [tests/test_bigquery.py](tests/test_bigquery.py) creates and destroys tables in the `ds_test` dataset of project `sf-da-dwh` (the hardcoded `DataLoader` default). Running the suite locally requires `gcloud auth application-default login` with access to that project. In CI, auth comes from the `GCP_SA_KEY` secret via `google-github-actions/auth@v2`. If you add a test that needs a SQL template, drop it under [tests/sql/](tests/sql/) and pass `root_package="tests"` to `run_query_from_template` — the package uses `importlib.resources` to locate templates, so they must live inside a Python package directory.

## Architecture

Two independent modules, both assuming `project="sf-da-dwh"`, `location="europe-west3"` by default:

- [ds_package_gcp/bigquery.py](ds_package_gcp/bigquery.py) — `DataLoader` class wrapping `google.cloud.bigquery.Client`. Read methods (`run_query`, `download_dataset`) pipe results through `convert_dbdate_to_datetime` from [utils.py](ds_package_gcp/utils.py) because pandas does not natively understand BigQuery's `dbdate` dtype. Write methods (`append_table`, `overwrite_table`, `replace_partition`) all coerce datetime columns to `.dt.date` before upload — passing a datetime column without that step will produce schema-mismatch errors. `append_table` has an explicit exponential-backoff retry loop (5 attempts) that retries only on `rateLimitExceeded`; other errors raise immediately. Both `replace_partition` (uploads a dataframe) and `replace_partition_from_query` (runs entirely server-side as a query job, no dataframe round-trip) scope the overwrite to one partition via partition-decorator syntax (`table$YYYYMMDD`) with `WRITE_TRUNCATE`. `replace_partition_from_query` copies the rows of a source table into one partition of an existing partitioned destination, stamping each row with the partition value in `partition_column`; with `partition_is_a_date=True` (default) it validates `partition_name` as `YYYY-MM-DD` and casts via `DATE(...)`, otherwise it treats the partition as a non-date value.
- [ds_package_gcp/vertex_ai.py](ds_package_gcp/vertex_ai.py) — `upload_model` / `load_model_artifact`. `upload_model` serializes the model with `joblib` into a local `temp_model.joblib`, uploads to `gs://{bucket}/models/{artifact_name}/{version_tag}/model.joblib` via `gcsfs`, then registers a new version under `parent_model` in Vertex AI Model Registry. The local `temp_model.joblib` is left in the working directory by design (a tracked empty file is committed at the repo root as a placeholder).

## Conventions in this repo

- Docstrings use a custom block format: `__ PARAMETERS __`, `__ RETURNS __`, `__ RAISES __` with `name: type` headers and indented descriptions. Match this style when adding public methods.
- Flake8 is configured with `max-line-length = 100` and ignores `E203, E266, E501, W503` (see [.flake8](.flake8)) — long lines won't fail lint, but `black` will still reformat them.
- The Docker image ([Dockerfile](Dockerfile)) is only used for consumer environments that need this package preinstalled with gcloud. Local dev does not require it.
