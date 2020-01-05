#Create an S3 bucket to store the code and provisioning the cloudformation stack 
import sys
import logging
import boto3
from botocore.exceptions import ClientError
import getopt
import botocore
import os
import random
import time
import json
from colorama import Fore, Back, Style
from colorama import init
import os.path
from os import path

# Usage
usageInfo = """Usage:
python init_cloud.py -p <codePath> -a <APIAccessKey> -s <APISecret> -b <Bucketname> -r <AWSRegion>
Type "python init_cloud.py -h" for available options.
"""
# Help info
helpInfo = """-a, --accessKey
	AWS User Access Key
-s, --secret
        AWS User Access Secret
-b, --bucket
        S3 Bucketname used as code repository
-p, --path
    local path where source code for Facerecognition Service is stored
-r, --region
    AWS Region where the stack and the bucket shall be created, if not specified US-EAST-1 will be taken
-h, --help
	Help information
"""
# File that stores the cloud and iot output parameter
filename = 'cloud_parameter.txt'

# Read in command-line parameters
path_cf = ""
access_key_id =""
secret_access_key=""
bucket_name=""
region = "us-east-1"

try:
    opts, args = getopt.getopt(sys.argv[1:], "hp:a:s:b:r:", ["help", "path=","accessKey=","secret=","bucket=","region="])
    if len(opts) == 0:
        raise getopt.GetoptError("No input parameters!")
    for opt, arg in opts:
        if opt in ("-h", "--help"):
            print(helpInfo)
            exit(0)
        if opt in ("-p", "--path"):
            path_cf = arg
        if opt in ("-a", "--accessKey"):
            access_key_id = arg
        if opt in ("-s", "--secret"):
            secret_access_key = arg
        if opt in ("-b", "--bucket"):
            bucket_name = arg
        if opt in ("-r", "--region"):
            region = arg
except getopt.GetoptError:
    print(usageInfo)
    exit(1)

# Missing configuration notification
missingConfiguration = False
if not path_cf:
	print("Missing '-p' or '--path'")
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

#initialize Cloudformation Parameter
cfYamlFile = "cf_FaceRekognitionService_V1.2.0.yaml"

def write_file(content, filename):
    f = open(filename,"w+")
    f.write(content)
    f.close()
    
def create_bucket(bucket_name, region):
    """Create an S3 bucket in a specified region

    If a region is not specified, the bucket is created in the S3 default
    region (us-east-1).

    :param bucket_name: S3 Bucket to create
    :param region: String region to create bucket in, e.g., 'us-west-2'
    :return: True if bucket created, else False
    """

    # Create bucket
    try:
        if region == 'us-east-1':
            s3_client = boto3.client('s3', aws_access_key_id=access_key_id,aws_secret_access_key=secret_access_key)
            s3_client.create_bucket(Bucket=bucket_name)
            print(Fore.GREEN + "Bucket "+bucket_name+" created in Region US-EAST-1! Continue with Upload of the objects" + Style.RESET_ALL)
        else:
            s3_client = boto3.client('s3', aws_access_key_id=access_key_id,aws_secret_access_key=secret_access_key,region_name=region)
            location = {'LocationConstraint': region}
            s3_client.create_bucket(Bucket=bucket_name,
                                    CreateBucketConfiguration=location)
            print(Fore.GREEN + "Bucket "+bucket_name+" created in Region "+region+"! Continue with Upload of the objects" + Style.RESET_ALL)
    except ClientError as e:
        error_code = (e.response['Error']['Code'])
        if error_code == 'BucketAlreadyOwnedByYou':
            print(Fore.YELLOW + "Bucket already exists! Continue with Upload of the objects" + Style.RESET_ALL)
        else:
            logging.error(e)
        return False
    return True

def upload_objects(bucket_name,source_path, region=None):
    """Upload Cloudformation files to S3 Code repository bucket

    :param bucket_name: Bucket to create
    :param region: String region to create bucket in, e.g., 'us-west-2'
    :return: True if bucket created, else None
    """
    if region == 'us-east-1':
        s3_resource = boto3.resource("s3",aws_access_key_id=access_key_id,aws_secret_access_key=secret_access_key)
    else:
        s3_resource = boto3.resource("s3", aws_access_key_id=access_key_id,aws_secret_access_key=secret_access_key,region_name=region)
    try:
        root_path = source_path # local folder for upload

        code_bucket = s3_resource.Bucket(bucket_name)

        print("Local source code path:", source_path)
        print("Uploading files to S3 bucket: "+bucket_name)
        for source_path, subdirs, files in os.walk(root_path):
            source_path = source_path.replace("\\","/")
  
            directory_name = source_path.replace(root_path,"")

            for file in files:
                print("Uploading file:", file)
                code_bucket.upload_file(os.path.join(source_path, file), directory_name+file)

    except Exception as err:
        print(err)
        return None
    return True

def create_presigned_url(bucket_name, object_name, region, expiration=600,):
    """Generate a presigned URL to share an S3 object

    :param bucket_name: string
    :param object_name: string
    :param expiration: Time in seconds for the presigned URL to remain valid
    :return: Presigned URL as string. If error, returns None.
    """
    if region == 'us-east-1':
        s3_client = boto3.client("s3",aws_access_key_id=access_key_id,aws_secret_access_key=secret_access_key)
    else:
        s3_client = boto3.client("s3", aws_access_key_id=access_key_id,aws_secret_access_key=secret_access_key,region_name=region)
    
    # Generate a presigned URL for the S3 object

    try:
        response = s3_client.generate_presigned_url('get_object',
                                                    Params={'Bucket': bucket_name,
                                                            'Key': object_name},
                                                    ExpiresIn=expiration)
    except ClientError as e:
        logging.error(e)
        return None

    # The response contains the presigned URL
    return response

def create_stack(bucket_name, region):
    """Create Cloudformation Stack

    :param bucket_name: string
    :param region: string
    :param template_url: Presigned S3 URL to the Cloudformation YAML file
    :param bucket_rekognition: S3 bucket used in the FaceRecognition Service, needs a random string to avoid conflicts
    :return: true If error, returns false.
    """    
    print("Start creating Cloudformation Stack for Face Recognition Service based on template:", cfYamlFile)
    template_url = create_presigned_url(bucket_name, cfYamlFile, region, expiration=600)
    global bucket_rekognition
    bucket_rekognition ='facerecognitionbucket'+str(random.randint(1000, 10000))
    
    try:
        client = boto3.client('cloudformation',aws_access_key_id=access_key_id,aws_secret_access_key=secret_access_key,region_name=region)
        print("Creating Cloudformation Stack")
        response = client.create_stack(
        StackName='FaceRecognitionStack',
        TemplateURL=template_url,
        Parameters=[
            {
                'ParameterKey': 'FaceRekognitionBucket',
                'ParameterValue': bucket_rekognition,
                'UsePreviousValue': True
            },
            {
                'ParameterKey': 'DynamoDBTableName',
                'ParameterValue': 'FaceRekognitionDB',
                'UsePreviousValue': True
            },
            {
                'ParameterKey': 'FaceRekognitionCollectionName',
                'ParameterValue': 'FaceRekognitionCollection',
                'UsePreviousValue': True
            },
            {
                'ParameterKey': 'CodeRepositoryBucket',
                'ParameterValue': bucket_name,
                'UsePreviousValue': True
            },
        ],
        Capabilities=[
            'CAPABILITY_IAM'
        ],
        OnFailure='DELETE',
        Tags=[
            {
                'Key': 'name',
                'Value': 'FaceRecognitionStack'
            },
        ],
        EnableTerminationProtection=False
    )
    except ClientError as e:
        logging.error(e)
        return False
    
    # get the StackID for output
    stackId = response['StackId']
    print("Stack creation started, your Stack ID is: ", stackId)
    required_status = 'CREATE_COMPLETE'
    data_status=""
    
    print ("Stack creation can take some time, please wait!")
    print("Let´s check the creation status. ")
    
    while data_status != required_status:
        try:
            data = client.describe_stacks(StackName = stackId)
            data_status = data['Stacks'][0]['StackStatus']

            if data_status == 'CREATE_IN_PROGRESS':
                print("Stack creation status:", data_status)
            elif data_status == 'CREATE_COMPLETE':
                print("Stack creation status:", data_status)
                print(Fore.GREEN + "Stack has been created successfully!" + Style.RESET_ALL)
                print("Your Bucketname for the Face Rekognition Service is:",bucket_rekognition)
                print("Please note down the Bucket name since it is required as parameter for the Facerognition Service scripts")
                print("You can now start recognizing new faces and start the recognition application")
                break
            else:
                print("Stack creation status:", data_status)
                print(Fore.RED + "Stack creation failed! Rollback and deletion of stack ressources in progress!"  + Style.RESET_ALL)
                print("Check Cloudformation events in AWS Console for further error details")
                break
            time.sleep(3)
        except ClientError as e:
            logging.error(e)
            return False
    return stackId
    

#------------------------------------------------------------------------------------------------------
if __name__ == '__main__':
        
        # initialize variables
        ul_response = ''
        cf_response = ''
        global bucket_rekognition
        bucket_rekognition = ''

        # check if path for cloud formation ressources exists
        if path.exists(path_cf):
            print(path_cf+cfYamlFile)
            
            # check if YAML file for Cloudformation exists
            if path.exists(path_cf+cfYamlFile):

                # Create an S3 bucket that will act as code repository for Cloudformation assets and upload files
                s3_response = create_bucket(bucket_name, region)
                if s3_response is True:
                    ul_response = upload_objects(bucket_name, path_cf, region)
                else:
                    print("Create Bucket failed!")
                if ul_response is True:
                    cf_response = create_stack(bucket_name, region)
                else:
                    print("File upload failed!")
                
                output={}
                if s3_response is not False:
                    output["region"] = region
                    output["code_bucket"] = bucket_name
                if cf_response is not False:
                    output["stack_id"] = cf_response
                    output["rekognition_bucket"] = bucket_rekognition
                
                # Write stack parameters to file   
                if output is not False:
                    if os.path.isfile(filename):
                        print (Fore.YELLOW + "Parameter file exists, deleting it" + Style.RESET_ALL)
                        os.remove(filename)
                    
                    write_file(json.dumps(output), filename)
                    print("Output Parameters are written to: "+ filename)
                else:
                    print(Fore.RED + "No output paramaters received, skipped writing file!" + Style.RESET_ALL)
            else:
                print(Fore.RED + "Cloudformation YAML file does not exist!" + Style.RESET_ALL)
        else:
            print(Fore.RED + "Directory for Cloudformation files does not exist!" + Style.RESET_ALL)