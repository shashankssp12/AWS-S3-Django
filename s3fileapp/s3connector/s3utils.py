import boto3 # Amazon's official Python package for working with AWS services
import mimetypes # To guess the MIME type of a file based on its filename
import requests # For making HTTP requests to the presigned URL
from django.conf import settings
from botocore.exceptions import ClientError # Catch AWS specific errors
import logging
import time 



logger = logging.getLogger(__name__) 

def get_s3_client():
    # creating and returning s3 client
    return boto3.client(
        's3',
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        region_name=settings.AWS_S3_REGION_NAME
    )
    
class S3Uploader:
    """Class for handling S3 file uploads with validation and duplicate handling"""
    
    def __init__(self):
        """Initialize the S3 uploader with AWS settings"""
        self.logger = logging.getLogger(__name__)
        self.bucket_name = settings.AWS_STORAGE_BUCKET_NAME
        self.s3_client = self._get_s3_client()
    
    def _get_s3_client(self):
        """Create and return an S3 client"""
        return boto3.client(
            's3',
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_S3_REGION_NAME
        )
    
    def _get_content_type(self, filename):
        """Determine the content type from the filename"""
        content_type, _ = mimetypes.guess_type(filename)
        if content_type is None:
            content_type = 'application/octet-stream'
        return content_type
    
    def _get_file_size_mb(self, file_obj):
        """Calculate file size in megabytes"""
        return file_obj.size / (1024 * 1024)
    
    def _check_for_duplicates(self, folder, filename):
        """Return a unique filename by adding a timestamp if needed"""
        original_key = f"{folder}/{filename}"
        
        # Check if file exists
        try:
            self.s3_client.head_object(Bucket=self.bucket_name, Key=original_key)
            
            # File exists, add timestamp
            timestamp = int(time.time())
            
            # Split filename to add timestamp before extension
            if '.' in filename:
                name, ext = filename.rsplit('.', 1)
                return f"{name}_{timestamp}.{ext}"
            else:
                return f"{filename}_{timestamp}"
                
        except:
            # File doesn't exist, use original name
            return filename
    
    def upload(self, file_obj, filename, folder="uploads", max_size_mb=500, large_file_threshold_mb=100):
        """
        Upload a file to S3 with duplicate handling
        
        Args:
            file_obj: The file object to upload
            filename: Name to give the file in S3
            folder: Folder path in the bucket (defaults to "uploads")
            max_size_mb: Maximum file size allowed (defaults to 500MB)
            large_file_threshold_mb: Size threshold to use different upload method (defaults to 100MB)
            
        Returns:
            dict: Upload result with success status and file info
        """
        # Check file size
        file_size_mb = self._get_file_size_mb(file_obj)
        
        if file_size_mb > max_size_mb:
            return {
                "success": False,
                "message": f"File too large. Maximum size is {max_size_mb}MB."
            }
        
        # Check for duplicates and get a unique filename
        unique_filename = self._check_for_duplicates(folder, filename)
        
        if unique_filename != filename:
            self.logger.info(f"Renamed file to avoid duplicate: {filename} → {unique_filename}")
        
        # Choose upload method based on file size
        if file_size_mb > large_file_threshold_mb:
            return self.upload_large_file(
                file_obj=file_obj,
                filename=unique_filename,
                folder=folder
            )
        else:
            return self.upload_small_file(
                file_obj=file_obj,
                filename=unique_filename,
                folder=folder
            )
    
    def upload_small_file(self, file_obj, filename, folder="uploads"):
        """
        Upload smaller files directly using upload_fileobj
        
        Args:
            file_obj: The file object to upload
            filename: Name to give the file in S3 (already checked for duplicates)
            folder: Folder path in the bucket
            
        Returns:
            dict: Upload result
        """
        content_type = self._get_content_type(filename)
        object_key = f"{folder}/{filename}"
        
        try:
            self.s3_client.upload_fileobj(
                file_obj,
                self.bucket_name,
                object_key,
                ExtraArgs={'ContentType': content_type}
            )
            
            self.logger.info(f"Successfully uploaded {filename} to {folder}")
            
            return {
                "success": True,
                "message": f"Successfully uploaded {filename}",
                "method": "standard",
                "file_info": {
                    "key": object_key,
                    "content_type": content_type,
                    "size_bytes": file_obj.size
                }
            }
        except ClientError as e:
            error_message = f"Error uploading file to S3: {e}"
            self.logger.error(error_message)
            return {"success": False, "message": error_message}
    
    def upload_large_file(self, file_obj, filename, folder="uploads"):
        """
        Upload larger files using presigned URL (backend handles it)
        
        Args:
            file_obj: The file object to upload
            filename: Name to give the file in S3 (already checked for duplicates)
            folder: Folder path in the bucket
            
        Returns:
            dict: Upload result
        """
        content_type = self._get_content_type(filename)
        object_key = f"{folder}/{filename}"
        
        try:
            # Generate a presigned URL for PUT operation
            presigned_url = self.s3_client.generate_presigned_url(
                'put_object',
                Params={
                    'Bucket': self.bucket_name,
                    'Key': object_key,
                    'ContentType': content_type
                },
                ExpiresIn=3600  # URL expires in 1 hour
            )
            
            # Reset file pointer to beginning
            file_obj.seek(0)
            
            # Upload the file using the presigned URL
            response = requests.put(
                presigned_url,
                data=file_obj,
                headers={'Content-Type': content_type}
            )
            
            if response.status_code == 200:
                self.logger.info(f"Successfully uploaded large file {filename} to {folder}")
                
                return {
                    "success": True,
                    "message": f"Successfully uploaded large file {filename}",
                    "method": "presigned_url",
                    "file_info": {
                        "key": object_key,
                        "content_type": content_type,
                        "size_bytes": file_obj.size
                    }
                }
            else:
                error_message = f"Error in presigned URL upload: {response.status_code} - {response.text}"
                self.logger.error(error_message)
                return {"success": False, "message": error_message}
                
        except Exception as e:
            error_message = f"Error uploading large file: {str(e)}"
            self.logger.error(error_message)
            return {"success": False, "message": error_message}
       
            
def list_files_in_s3():
    s3_client = get_s3_client()
    try:
        response = s3_client.list_objects_v2(
            Bucket = settings.AWS_STORAGE_BUCKET_NAME,
            Prefix='uploads/'
        )
        files=[]
        if 'Contents' in response:
            for obj in response['Contents']:
                 # Remove the 'uploads/' prefix for display
                filename = obj['Key'].replace('uploads/','',1)
                if filename:
                    files.append({
                        'filename': filename,
                        'size': obj['Size'],
                        'last_modified': obj['LastModified']
                    })
        logger.info(f'Successfully listed {len(files)} files from the S3 bucket')
        return files
    except ClientError as e: 
        logger.error(f'Error listing the files in S3: {e}')
        return []  
    
def create_download_link(filename):
    """Generate a presigned URL for downloading a file"""
    s3_client = get_s3_client()
    try:
        # Generate a presigned URL that expires in 3600 seconds (1 hour)
        response = s3_client.generate_presigned_url(
            'get_object',
            Params={
                'Bucket': settings.AWS_STORAGE_BUCKET_NAME,
                'Key': f"uploads/{filename}"
            },
            ExpiresIn=3600
        )
        logger.info(f"Generated presigned URL for {filename}")
        return response
    except ClientError as e:
        logger.error(f"Error generating presigned URL: {e}")
        return None

def delete_file_from_s3(filename):
    """Delete a file from S3 bucket"""
    s3_client = get_s3_client()
    try:
        s3_client.delete_object(
            Bucket=settings.AWS_STORAGE_BUCKET_NAME,
            Key=f"uploads/{filename}"
        )
        logger.info(f"Successfully deleted file: {filename}")
        return True
    except ClientError as e:
        logger.error(f"Error deleting file from S3: {e}")
        return False