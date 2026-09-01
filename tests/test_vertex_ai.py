from ds_package_gcp.vertex_ai import upload_model, load_model_artifact


def test_upload_and_download_model():

    model = {"x": 1, "y": 2}

    # upload model to registry
    _ = upload_model(
        bucket_name="gs://ds-pipelines-outputs",
        parent_model="projects/634307141317/locations/europe-west3/models/3610633457895473152",
        artifact_name="ds_package_gcp_test_model",
        model_name="ds-package-gcp-test-model",
        model=model,
        serving_container_image_uri="europe-west3-docker.pkg.dev/sf-da-dwh/ds-images/ds-gcp-test-base:latest",
        version_tag="test_v1",
    )

    # download model from registry
    loaded_model, _ = load_model_artifact(
        model_registry_model="projects/634307141317/locations/europe-west3/models/3610633457895473152",
    )

    assert loaded_model is not None
