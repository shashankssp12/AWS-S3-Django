import boto3 # Amazon's official Python package for working with AWS services
from django.conf import settings
from botocore.exceptions import ClientError # Catch AWS specific errors
import logging

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


def test_upload():
    with open('test.txt','rb') as file:
        success = upload_file_to_s3(file, 'test.txt')
        
        if success:
            logger.info("File uploaded successfully!")
        else:
            logger.error("File upload failed")