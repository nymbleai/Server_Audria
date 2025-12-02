import pypandoc
import tempfile
import os
from typing import Optional
from fastapi import UploadFile
import logging

logger = logging.getLogger(__name__)

class FileConverterService:
    @staticmethod
    async def convert_docx_to_html(file: UploadFile) -> Optional[str]:
        try:
            content = await file.read()
            with tempfile.NamedTemporaryFile(suffix='.docx', delete=False) as temp_docx:
                temp_docx.write(content)
                temp_docx_path = temp_docx.name
            try:
                try:
                    html_content = pypandoc.convert_file(
                        temp_docx_path,
                        'html',
                        format='docx'
                    )
                    return html_content
                except OSError as e:
                    if "No pandoc was found" in str(e):
                        logger.warning("Pandoc not found, attempting to download...")
                        try:
                            pypandoc.download_pandoc()
                            html_content = pypandoc.convert_file(
                                temp_docx_path,
                                'html',
                                format='docx'
                            )
                            return html_content
                        except Exception as download_error:
                            logger.error(f"Failed to download pandoc: {download_error}")
                            raise Exception("Pandoc installation failed. Please install pandoc manually: brew install pandoc (macOS) or sudo apt-get install pandoc (Ubuntu)")
                    else:
                        raise e
            finally:
                if os.path.exists(temp_docx_path):
                    os.unlink(temp_docx_path)
        except Exception as e:
            logger.error(f"Error converting DOCX to HTML: {e}")
            return None

    @staticmethod
    def is_docx_file(file: UploadFile) -> bool:
        if not file.filename:
            return False
        return (
            file.filename.lower().endswith('.docx') or 
            file.content_type == 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        )

file_converter_service = FileConverterService() 