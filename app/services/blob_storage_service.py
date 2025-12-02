from google.cloud import storage
from google.cloud.exceptions import NotFound, GoogleCloudError
from app.core.config import settings
from typing import Optional, Union
import asyncio
from functools import wraps
import logging
import os

logger = logging.getLogger(__name__)

class BlobStorageService:
    def __init__(self):
        self.storage_client = None
        self.bucket = None
        
        if settings.google_application_credentials and settings.gcs_bucket_name:
            try:
                credentials_str = settings.google_application_credentials.strip()
                
                # Check if it's JSON content or file path
                if credentials_str.startswith('{') and credentials_str.endswith('}'):
                    # JSON content - create temporary file
                    import json
                    import tempfile
                    
                    print("🔧 Processing JSON credentials...")
                    credentials_dict = json.loads(credentials_str)
                    
                    # Create temporary file
                    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as temp_file:
                        json.dump(credentials_dict, temp_file)
                        temp_credentials_path = temp_file.name
                    
                    print(f"🔧 Created temporary credentials file: {temp_credentials_path}")
                    os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = temp_credentials_path
                else:
                    # File path
                    print(f"🔧 Using credentials file: {credentials_str}")
                    os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = credentials_str
                
                # Initialize the storage client
                print("🔧 Initializing Google Cloud Storage client...")
                self.storage_client = storage.Client()
                self.bucket = self.storage_client.bucket(settings.gcs_bucket_name)
                
                # Check if bucket exists, create if it doesn't
                if not self.bucket.exists():
                    self.bucket = self.storage_client.create_bucket(settings.gcs_bucket_name)
                    logger.info(f"✅ Created new bucket: {settings.gcs_bucket_name}")
                
                print("✅ Google Cloud Storage client initialized successfully")
            except Exception as e:
                print(f"❌ Warning: Failed to initialize Google Cloud Storage client: {e}")
                self.storage_client = None
                self.bucket = None
        else:
            print("❌ Warning: Google Cloud Storage credentials or bucket name not provided")

    def _check_client(self):
        if not self.storage_client or not self.bucket:
            raise Exception("Google Cloud Storage client not initialized. Check your GOOGLE_APPLICATION_CREDENTIALS and GCS_BUCKET_NAME.")

    async def upload_file(self, blob_path: str, content: Union[bytes, str], content_type: str = None) -> bool:
        """
        Upload a file to Google Cloud Storage
        
        Args:
            blob_path: The path/name for the blob
            content: The file content (bytes or string)
            content_type: MIME type of the content
            
        Returns:
            bool: True if upload successful, False otherwise
        """
        self._check_client()
        
        try:
            # Convert string content to bytes if needed
            if isinstance(content, str):
                content = content.encode('utf-8')
            
            blob = self.bucket.blob(blob_path)
            
            # Upload the content
            blob.upload_from_string(
                content,
                content_type=content_type
            )
            
            logger.info(f"✅ Successfully uploaded file to Google Cloud Storage: {blob_path}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to upload file to Google Cloud Storage: {e}")
            return False

    async def download_file(self, blob_path: str) -> Optional[bytes]:
        """
        Download a file from Google Cloud Storage
        
        Args:
            blob_path: The path/name of the blob to download
            
        Returns:
            bytes: The file content, or None if download failed
        """
        self._check_client()
        
        try:
            blob = self.bucket.blob(blob_path)
            
            # Download the blob
            content = blob.download_as_bytes()
            
            logger.info(f"✅ Successfully downloaded file from Google Cloud Storage: {blob_path}")
            return content
            
        except NotFound:
            logger.warning(f"⚠️ File not found in Google Cloud Storage: {blob_path}")
            return None
        except Exception as e:
            logger.error(f"❌ Failed to download file from Google Cloud Storage: {e}")
            return None

    async def delete_file(self, blob_path: str) -> bool:
        """
        Delete a file from Google Cloud Storage
        
        Args:
            blob_path: The path/name of the blob to delete
            
        Returns:
            bool: True if deletion successful, False otherwise
        """
        self._check_client()
        
        try:
            blob = self.bucket.blob(blob_path)
            blob.delete()
            
            logger.info(f"✅ Successfully deleted file from Google Cloud Storage: {blob_path}")
            return True
            
        except NotFound:
            logger.warning(f"⚠️ File not found in Google Cloud Storage for deletion: {blob_path}")
            return True  # Consider it successful if file doesn't exist
        except Exception as e:
            logger.error(f"❌ Failed to delete file from Google Cloud Storage: {e}")
            return False

    async def file_exists(self, blob_path: str) -> bool:
        """
        Check if a file exists in Google Cloud Storage
        
        Args:
            blob_path: The path/name of the blob to check
            
        Returns:
            bool: True if file exists, False otherwise
        """
        self._check_client()
        
        try:
            blob = self.bucket.blob(blob_path)
            blob.reload()  # This will raise NotFound if blob doesn't exist
            return True
        except NotFound:
            return False
        except Exception as e:
            logger.error(f"❌ Error checking file existence in Google Cloud Storage: {e}")
            return False

    async def get_file_url(self, blob_path: str, expires_in: int = 3600) -> Optional[str]:
        """
        Get a temporary URL for a file in Google Cloud Storage
        
        Args:
            blob_path: The path/name of the blob
            expires_in: URL expiration time in seconds (default: 1 hour)
            
        Returns:
            str: Temporary URL, or None if failed
        """
        self._check_client()
        
        try:
            blob = self.bucket.blob(blob_path)
            
            # Generate a signed URL
            url = blob.generate_signed_url(
                version="v4",
                expiration=expires_in,
                method="GET"
            )
            
            return url
            
        except Exception as e:
            logger.error(f"❌ Failed to generate file URL: {e}")
            return None

# Create a singleton instance
blob_storage_service = BlobStorageService() 