import os
import httpx
import aiofiles
from typing import List, Optional, Dict, Any
from pathlib import Path
import logging
from app.core.config import settings

logger = logging.getLogger(__name__)

class IngestionFileService:
    """Service for downloading and storing ingestion files locally"""
    
    def __init__(self):
        self.storage_path = Path("/app/data/ingestion_files")
        self.storage_path.mkdir(parents=True, exist_ok=True)
    
    def _get_job_directory(self, job_id: str) -> Path:
        """Get the directory path for a specific job"""
        job_dir = self.storage_path / job_id
        job_dir.mkdir(parents=True, exist_ok=True)
        return job_dir
    
    def _get_file_extension(self, file_type: str) -> str:
        """Determine file extension based on file type"""
        return "csv" if file_type.endswith("_csv") else "json"
    
    async def download_job_file(self, job_id: str, file_type: str) -> Optional[str]:
        """
        Download a specific file from ingestion job and store it locally.
        
        Args:
            job_id: The ingestion job ID
            file_type: Type of file to download (e.g., 'chunks_csv', 'structure_extraction_json')
        
        Returns:
            Local file path if successful, None if failed
        """
        try:
            logger.info(f"📥 Downloading ingestion file: job_id={job_id}, file_type={file_type}")
            
            # Get job directory
            job_dir = self._get_job_directory(job_id)
            
            # Determine filename and path
            file_extension = self._get_file_extension(file_type)
            filename = f"{file_type}.{file_extension}"
            local_file_path = job_dir / filename
            
            # Download from ingestion API
            async with httpx.AsyncClient(timeout=settings.ingestion_api_timeout) as client:
                response = await client.get(
                    f"{settings.ingestion_api_url}/job/{job_id}/download/{file_type}",
                    headers={"accept": "application/json"}
                )
                
                if response.status_code == 200:
                    # Write file to local storage
                    async with aiofiles.open(local_file_path, 'wb') as f:
                        await f.write(response.content)
                    
                    logger.info(f"✅ File downloaded successfully: {local_file_path}")
                    return str(local_file_path)
                else:
                    logger.error(f"❌ Failed to download file: HTTP {response.status_code}")
                    return None
                    
        except Exception as e:
            logger.error(f"❌ Error downloading file: {str(e)}")
            return None
    
    async def _get_available_file_types(self, job_id: str) -> List[str]:
        """
        Get the list of available file types for a job by calling the files endpoint.
        
        Returns:
            List of available file type names
        """
        try:
            async with httpx.AsyncClient(timeout=settings.ingestion_api_timeout) as client:
                response = await client.get(
                    f"{settings.ingestion_api_url}/job/{job_id}/files",
                    headers={"Content-Type": "application/json"}
                )
                
                if response.status_code == 200:
                    data = response.json()
                    files = data.get('files', [])
                    # Extract file types from the response
                    file_types = []
                    for file_info in files:
                        file_type = file_info.get('file_type')
                        if file_type:
                            file_types.append(file_type)
                    
                    logger.info(f"🔍 Discovered {len(file_types)} available file types for job {job_id}")
                    return file_types
                else:
                    logger.warning(f"⚠️ Could not get file list for job {job_id}, using fallback list")
                    # Fallback to the known file types if API call fails
                    return self._get_fallback_file_types()
        except Exception as e:
            logger.error(f"❌ Error getting available files for job {job_id}: {str(e)}")
            return self._get_fallback_file_types()
    
    def _get_fallback_file_types(self) -> List[str]:
        """Fallback list of common file types"""
        return [
            "chunks_csv",
            "structure_extraction_json", 
            "non_clauses_json",
            "cross_references_json",
            "defined_terms_json",
            "sections_chapters_csv",
            "structural_elements_csv",
            "xrefs_csv",
            "definitions_csv"
        ]

    async def download_all_job_files(self, job_id: str) -> Dict[str, Optional[str]]:
        """
        Download all available files for a job.
        
        First discovers what files are actually available for this job,
        then downloads only those files.
        
        Args:
            job_id: The ingestion job ID
            
        Returns:
            Dictionary mapping file_type to local_path (None if download failed)
        """
        logger.info(f"📦 Discovering and downloading all files for job: {job_id}")
        
        # First, get the list of available file types for this specific job
        file_types = await self._get_available_file_types(job_id)
        
        if not file_types:
            logger.warning(f"⚠️ No file types discovered for job {job_id}")
            return {}
        
        results = {}
        
        for file_type in file_types:
            local_path = await self.download_job_file(job_id, file_type)
            results[file_type] = local_path
        
        successful_downloads = sum(1 for path in results.values() if path is not None)
        logger.info(f"✅ Downloaded {successful_downloads}/{len(file_types)} files for job {job_id}")
        
        return results
    
    def get_local_file_path(self, job_id: str, file_type: str) -> Optional[str]:
        """Get the local path of a previously downloaded file"""
        job_dir = self._get_job_directory(job_id)
        file_extension = self._get_file_extension(file_type)
        filename = f"{file_type}.{file_extension}"
        local_file_path = job_dir / filename
        
        if local_file_path.exists():
            return str(local_file_path)
        return None
    
    def list_job_files(self, job_id: str) -> List[Dict[str, Any]]:
        """List all locally stored files for a job"""
        job_dir = self._get_job_directory(job_id)
        files = []
        
        if job_dir.exists():
            for file_path in job_dir.iterdir():
                if file_path.is_file():
                    files.append({
                        "filename": file_path.name,
                        "full_path": str(file_path),
                        "size_bytes": file_path.stat().st_size,
                        "file_type": file_path.stem  # filename without extension
                    })
        
        return files
    
    def cleanup_job_files(self, job_id: str) -> bool:
        """Remove all files for a specific job"""
        try:
            job_dir = self._get_job_directory(job_id)
            if job_dir.exists():
                import shutil
                shutil.rmtree(job_dir)
                logger.info(f"🗑️ Cleaned up files for job: {job_id}")
                return True
            return False
        except Exception as e:
            logger.error(f"❌ Error cleaning up job files: {str(e)}")
            return False

# Create singleton instance
ingestion_file_service = IngestionFileService() 