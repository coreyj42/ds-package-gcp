import joblib
import gcsfs
from google.cloud import aiplatform
from typing import Optional


def upload_model(
    bucket_name: str,
    parent_model: str,
    artifact_name: str,
    model_name: str,
    model: object,
    serving_container_image_uri: str,
    version_tag: str,
) -> aiplatform.Model:
    """
    Uploads a trained model to a GCS bucket and registers it as a new version in Vertex AI Model Registry.

    __ PARAMETERS __
    bucket_name: str
        Name of the GCS bucket where the model artifact will be stored.
    parent_model: str
        Full resource name of the existing Vertex AI model to which this version will be added.
    artifact_name: str
        Name of model artifact folder in bucket
    model_name: str
        Display name for the model version in Vertex AI Model Registry.
    model: object
        The trained model instance to be serialized and uploaded.
    serving_container_image_uri: str
        URI of the container image used to serve the model.
    version_tag: str
        Custom tag to identify the version.

    __ RETURNS __
    aiplatform.Model
        The registered Vertex AI model version object created after upload.
    """

    # Initialize Vertex AI
    aiplatform.init(project="sf-da-dwh", location="europe-west3")

    # Save model locally in a temp file
    joblib.dump(model, "temp_model.joblib")

    # Upload to GCS
    fs = gcsfs.GCSFileSystem()
    model_uri = f"{bucket_name}/models/{artifact_name}/{version_tag}"
    fs.put("temp_model.joblib", f"{model_uri}/model.joblib")

    # Create model in registry
    vertex_model = aiplatform.Model.upload(
        parent_model=parent_model,
        display_name=model_name,
        artifact_uri=model_uri,
        serving_container_image_uri=serving_container_image_uri,
    )

    return vertex_model


def load_model_artifact(
    model_registry_model: str, version: Optional[int] = None
) -> tuple[object, str]:
    """
    Loads a serialized model artifact from Vertex AI Model Registry by retrieving
    the associated artifact stored in GCS.

    __ PARAMETERS __
    model_registry_model: str
        Full resource name of the registered Vertex AI model.
    version: Optional[int]
        Specific model version to load. If None, the default/latest version is used.

    __ RETURNS __
    tuple[object, str]
        A tuple containing:
        - The deserialized model artifact
        - The version tag associated with the artifact
    """

    # Initialize Vertex AI
    aiplatform.init(project="sf-da-dwh", location="europe-west3")

    # Get model artifact location from model registry
    model = aiplatform.Model(model_name=model_registry_model, version=version)
    artifact_loaction = f"{model.uri}/model.joblib"

    # Load model artifact
    fs = gcsfs.GCSFileSystem(project="sf-da-dwh", location="europe-west3")
    with fs.open(artifact_loaction, "rb") as f:
        model_artifact = joblib.load(f)

    # Get version tag
    version_tag = artifact_loaction.replace("gs://", "").split("/")[-2]

    return model_artifact, version_tag
