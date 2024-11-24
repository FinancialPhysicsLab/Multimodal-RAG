from google.cloud import storage
import io
from PIL import Image
import keys

GCP_SERVICE_ACCOUNT = keys.GCP_SERVICE_ACCOUNT

def list_objects_in_bucket(bucket_name):
    """Lists all the objects in the bucket."""
    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)
    blobs = bucket.list_blobs()
    return [blob.name for blob in blobs]

def read_pdf_from_gcs(bucket_name, source_blob_name):
    """Reads a PDF file from GCS and returns it as a bytes object."""
    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(source_blob_name)
    if not blob.exists():
        raise FileNotFoundError(f"No such object: {bucket_name}/{source_blob_name}")
    pdf_bytes = blob.download_as_bytes()
    return pdf_bytes

def create_bucket(bucket_name):
    """Creates a new bucket."""
    # Initialize a client
    storage_client = storage.Client()

    # Create a new bucket
    bucket = storage_client.create_bucket(bucket_name)


def create_folder(bucket_name, folder_name):
    """Creates a folder-like structure within a bucket."""
    # Initialize a client
    storage_client = storage.Client()

    # Get the bucket
    bucket = storage_client.get_bucket(bucket_name)

    # Create a blob with the folder name and a trailing slash
    blob = bucket.blob(f"{folder_name}/")

    # Upload an empty string to create the folder
    blob.upload_from_string('')

def upload_file_to_folder(bucket_name, folder_name, file, file_name, type='file'):
    """Uploads a file to a specified folder within a bucket."""
    # Initialize a client
    storage_client = storage.Client()

    # Get the bucket
    bucket = storage_client.get_bucket(bucket_name)

    # Create a blob with the folder name and file name
    blob = bucket.blob(f"{folder_name}/{file_name}")

    # Upload the file content
    if type == 'file':
        blob.upload_from_file(file)
    else:
        blob.upload_from_string(file)

def get_image_from_gcp(bucket_name, folder, file_name):
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(f"{folder}/{file_name}")
    image_data = blob.download_as_bytes()
    image = Image.open(io.BytesIO(image_data))
    return image