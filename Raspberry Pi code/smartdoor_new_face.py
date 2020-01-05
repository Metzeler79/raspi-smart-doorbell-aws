'''Used for creating new user in AWS with Face recognition and DynamoDB (so that this user can be authenticated at the door)
    - Take a picture of the User
    - Upload it to the S3 Bucket
    - Not handled in this function, for information only -> 
        - Upload triggers Lambda Function "IndexFaces"
        - Lambda triggers Face Rekognition to create a new profile/match ID for the User
        - Lambda triggers DynamoDB and creates an entry with the User name (name parameter from commandline) and the Face Match ID from Rekognition
# The code for this project is inspired and based on: https://softwaremill.com/access-control-system-with-rfid-and-amazon-rekognition/
  
'''
import sys
import logging
import time
import json
import random
import getopt
import picamera
import os
import boto3
from botocore.exceptions import ClientError

# Usage
usageInfo = """Usage:
python smartdoor_new_face.py -n <name> -a <APIAccessKey> -s <APISecret> -b <Bucketname>
Type "python smartdoor_new_face.py -h" for available options.
"""
# Help info
helpInfo = """-n, --name
	Name of the new user
-a, --accessKey
	AWS User Access Key
-s, --secret
        AWS User Access Secret
-b, --bucket
        S3 Bucketname that was provisioned for FaceRecognition Service
-h, --help
	Help information
"""

# Read in command-line parameters
name = ""
access_key_id =""
secret_access_key=""
bucket_name=""

try:
    opts, args = getopt.getopt(sys.argv[1:], "hn:a:s:b:", ["help", "name=","accessKey=","secret=","bucket="])
    if len(opts) == 0:
        raise getopt.GetoptError("No input parameters!")
    for opt, arg in opts:
        if opt in ("-h", "--help"):
            print(helpInfo)
            exit(0)
        if opt in ("-n", "--name"):
            name = arg
        if opt in ("-a", "--accessKey"):
            access_key_id = arg
        if opt in ("-s", "--secret"):
            secret_access_key = arg
        if opt in ("-b", "--bucket"):
            bucket_name = arg
except getopt.GetoptError:
    print(usageInfo)
    exit(1)

# Missing configuration notification
missingConfiguration = False
if not name:
	print("Missing '-n' or '--name'")
	missingConfiguration = True
if not access_key_id:
    print("Missing '-a' or '--accessKey'")
    missingConfiguration = True
if not secret_access_key:
    print("Missing '-s' or '--secret'")
    missingConfiguration = True
if not bucket_name:
    print("Missing '-b' or '--bucket'")
    missingConfiguration = True
if missingConfiguration:
	exit(2)

#--------------------------------- Initialization --------------------------------------------
# photo properties
image_width = 800
image_height = 600
file_extension = '.jpg'

# camera setup
camera = picamera.PiCamera()
camera.resolution = (image_width, image_height)
camera.awb_mode = 'auto'

def takePhoto(file_name):
    ''' takes a picture of the user
    file_name is the user name that was set with the name parameter on command line
    '''
    filepath = file_name + file_extension
    camera.capture(filepath)
    
def uploadToS3(file_name):
    ''' Uploads the User Picture to S3 Bucket
    Upload triggers Lambda Function "Index Faces"
    '''
    
    filepath = file_name + file_extension
    
    # Metadata header "x-amz-meta-fullname" header is required for Lambda function to create an entry with te name in DynamoDB later
    try:
        client = boto3.client('s3',aws_access_key_id=access_key_id,aws_secret_access_key=secret_access_key)
        response = client.upload_file(filepath, bucket_name, "index/" + filepath,ExtraArgs={'Metadata': {'cache-control': 'max-age=60','fullname': name}})
    except ClientError as e:
        logging.error(e)
        return False
    return True

    if os.path.exists(filepath):
        os.remove(filepath)
        
#--------------------------------- Main Loop --------------------------------------------

#--------------------------------- Main function --------------------------------------------
if __name__ == '__main__':
    print("We must take a picture from " + name + " to create the authentication entry.")
    input("Please look into the camera and press ENTER when ready.")
    takePhoto(name)
    uploadToS3(name)
    print("Thats it. You should now be able to authenticate at the door.")
	
