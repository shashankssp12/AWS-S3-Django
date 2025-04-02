import boto3 # Amazon's official Python package for working with AWS services
from django.conf import settings
from botocore.exceptions import ClientError # Catch AWS specific errors
import logging
import os
logger = logging.getLogger(__name__) 

def get_s3_client():
    # creating and returning s3 client
    return boto3.client(
        's3',
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        region_name=settings.AWS_S3_REGION_NAME
    )
    
def test_connection():
    # let's test if we can see the s3 bucket list and it will have the buucket that ii've created
    try:
        s3_client = get_s3_client()
        response = s3_client.list_buckets()
        buckets = [bucket['Name'] for bucket in response['Buckets']]
        logger.info(f'Connection successful! Your buckets: {buckets}') # the info level loggers dont showupu in the console during development by default
        return True 
    except Exception as e:
        logger.error(f"Connection failed: {e}")
        return False
    
def upload_file_to_s3(file_obj, filename):
    s3_client = get_s3_client()
    try: 
        s3_client.upload_fileobj(
            file_obj,
            settings.AWS_STORAGE_BUCKET_NAME,
            f"uploads/{filename}"
        )
        logger.info(f"Successsfuully uploaded file: {filename}")
        return True
    except ClientError as e: 
        logger.error(f"Error uploading file to S3: {e}")
        return False



def test_upload_multiple_files():
    """Test uploading multiple files of different types from the test-uploads folder"""
    # Get the current working directory (where manage.py is)
    current_dir = os.getcwd()
    
    # Go up one level to the parent directory
    parent_dir = os.path.dirname(current_dir)
    
    # Path to your uploads folder
    upload_folder = os.path.join(parent_dir, 'resources', 'test-uploads')
    
    # Check if folder exists
    if not os.path.exists(upload_folder):
        logger.error(f"Folder {upload_folder} does not exist")
        return False
    
    # Get list of files in the folder
    files = os.listdir(upload_folder)
    logger.info(f"Found {len(files)} files in {upload_folder}")
    
    # Track success/failure
    successful = []
    failed = []
    
    # Try to upload each file
    for filename in files:
        # Get the full path to the file
        file_path = os.path.join(upload_folder, filename)
        
        # Skip directories
        if os.path.isdir(file_path):
            continue
        
        # Open and upload the file
        try:
            with open(file_path, 'rb') as file_obj:
                logger.info(f"Attempting to upload {filename}")
                success = upload_file_to_s3(file_obj, filename)
                
                if success:
                    successful.append(filename)
                    logger.info(f"Successfully uploaded {filename}")
                else:
                    failed.append(filename)
                    logger.error(f"Failed to upload {filename}")
        except Exception as e:
            failed.append(filename)
            logger.error(f"Error uploading {filename}: {e}")
    
    # Summary
    logger.info(f"Upload test complete. {len(successful)} successful, {len(failed)} failed")
    logger.info(f"Successful uploads: {successful}")
    if failed:
        logger.warning(f"Failed uploads: {failed}")
    
    # Return True if all uploads were successful
    return len(failed) == 0
            
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

def test_create_download_link():
    """Test function for creating and verifying download links"""
    try:
        # First, list all files to see what's available
        files = list_files_in_s3()
        logger.info(f"Available files: {[f['filename'] for f in files]}")
        
        # Choose a file from the list and create a download link
        if files:
            filename = files[0]['filename']  # Get the first file
            download_url = create_download_link(filename)
            logger.info(f"Download link for {filename}:")
            logger.info(download_url)
            logger.info("This link will work for 1 hour")
            return download_url
        else:
            logger.warning("No files found in the bucket")
            return None
    except Exception as e:
        logger.error(f"Error in test_create_download_link: {e}")
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