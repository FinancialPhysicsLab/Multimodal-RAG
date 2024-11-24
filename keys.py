import dotenv
import os

# load environment variables
load_status = dotenv.load_dotenv(".env")
if load_status is False:
    raise RuntimeError('Environment variables are not found.')

NEO4J_URI = os.getenv("NEO4J_URI")
NEO4J_USERNAME = os.getenv('NEO4J_USERNAME')
NEO4J_PASSWORD = os.getenv('NEO4J_PASSWORD')
AURA_INSTANCEID = os.getenv('AURA_INSTANCEID')
AURA_INSTANCENAME = os.getenv('AURA_INSTANCENAME')
GEMINI_MODEL: str = os.getenv("GEMINI_MODEL")
GEMINI_IMAGE_MODEL: str = os.getenv("GEMINI_IMAGE_MODEL")
EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL")
GOOGLE_API_KEY: str = os.getenv("GOOGLE_API_KEY")
FIRESTORE_URL: str = os.getenv("FIRESTORE_URL")
FIRESTORE_API_KEY: str = os.getenv("FIRESTORE_API_KEY")
GCP_BUCKET: str = os.getenv("GCP_BUCKET")
GCP_SERVICE_ACCOUNT: str = os.getenv("GCP_SERVICE_ACCOUNT")
GCP_PROJECT_ID: str = os.getenv("GCP_PROJECT_ID")
GCP_LOCATION: str = os.getenv("GCP_LOCATION")

