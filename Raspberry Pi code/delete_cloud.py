import sys
import logging
import boto3
from botocore.exceptions import ClientError
import getopt
import botocore
import os
import json
import time
import re
from colorama import Fore, Back, Style
from colorama import init

# Usage
usageInfo = """Usage:
python delete_cloud.py -a <APIAccessKey> -s <APISecret>
Type "python delete_cloud.py -h" for available options.
"""
# Help info
helpInfo = """-a, --accessKey
	AWS User Access Key
-s, --secret
        AWS User Access Secret
-h, --help
	Help information
"""

# Default Filename
cloudFile = 'cloud_parameter.txt'
iotFile = 'iot_parameter.txt'
region = None

# Read in command-line parameters
access_key_id =""
secret_access_key=""

try:
    opts, args = getopt.getopt(sys.argv[1:], "hf:a:s:", ["help", "file=","accessKey=","secret="])
    if len(opts) == 0:
        raise getopt.GetoptError("No input parameters!")
    for opt, arg in opts:
        if opt in ("-h", "--help"):
            print(helpInfo)
            exit(0)
        if opt in ("-a", "--accessKey"):
            access_key_id = arg
        if opt in ("-s", "--secret"):
            secret_access_key = arg
except getopt.GetoptError:
    print(usageInfo)
    exit(1)

# Missing configuration notification
missingConfiguration = False
if not access_key_id:
    print("Missing '-a' or '--accessKey'")
    missingConfiguration = True
if not secret_access_key:
    print("Missing '-s' or '--secret'")
    missingConfiguration = True
if missingConfiguration:
	exit(2)


def del_cfstack(stackId, region):
    ''' checks if the cloud formation stack exists and deletes it
        :param stackId: AWS Stack ID
        :param region: AWS region for the stack
        :return: True if successfully deleted, False if error occurs
    '''
    try:
        client = boto3.client('cloudformation',aws_access_key_id=access_key_id,aws_secret_access_key=secret_access_key,region_name=region)

        # Check if stack exists before executing delete
        try:
            data = client.describe_stacks(StackName = stackId)
            data_status = data['Stacks'][0]['StackStatus']
        except ClientError:
            print(Fore.YELLOW + "Stack does not exist! Delete canceled" + Style.RESET_ALL)
            return False
        # Just delete the Stack if the status is "CREATE_COMPLETE"
        if data_status == 'CREATE_COMPLETE':       
            response = client.delete_stack(
                StackName=stackId)
        
            required_status = 'DELETE_COMPLETE'
            data_status=""

            print ("Stack deletion can take some time, please wait!")
            print("Let´s check the deletion status. ")

            # Check deletion status in a loop
            while data_status != required_status:
                try:
                    data = client.describe_stacks(StackName = stackId)
                    data_status = data['Stacks'][0]['StackStatus']

                    if data_status == 'DELETE_IN_PROGRESS':
                        print("Stack deletion status:", data_status)
                    elif data_status == 'DELETE_COMPLETE':
                        print("Stack deletion status:", data_status)
                        print(Fore.GREEN + "Stack has been deleted successfully!" + Style.RESET_ALL)
                        break
                    else:
                        print("Stack deletion status:", data_status)
                        print(Fore.RED + "Stack deletion failed! ")
                        print("Check Cloudformation events in AWS Console for further error details" + Style.RESET_ALL)
                        break
                    time.sleep(3)
                except ClientError as e:
                    logging.error(e)
                    return False
        else:
            print(Fore.YELLOW + "Stack does not exist! Delete canceled" + Style.RESET_ALL)
    except ClientError as e:
            logging.error(e)
            return False
    return True


def del_s3files(bucket):
    ''' Delete files on S3 bucket
        :param bucket: AWS S3 bucket name
        :return: True if successfully deleted, False if error occurs
    '''
    try:
        s3 = boto3.resource('s3',aws_access_key_id=access_key_id,aws_secret_access_key=secret_access_key,region_name=region)
            
        bucket = s3.Bucket(bucket)
        bucket.objects.all().delete()
        return True
    except ClientError as e:
            logging.error(e)
            return False



def del_s3bucket(bucket,region):
    ''' Delete S3 bucket
        :param bucket: AWS S3 bucket name
        :return: True if successfully deleted, False if error occurs
    '''
    try:
        s3 = boto3.resource('s3',aws_access_key_id=access_key_id,aws_secret_access_key=secret_access_key,region_name=region)
        
        bucket = s3.Bucket(bucket)
        bucket.delete()
        return True
    except ClientError as e:
            logging.error(e)
            return False

        
def del_iotthing(thingName, region):
    ''' Delete iot Thing on AWS Iot Core
        :param thingName: AWS IoT Thing name to delete
        :param region: AWS region where thing was created
        :return: True if successfully deleted, False if error occurs
    '''
    try: 

        iot_client = boto3.client('iot', aws_access_key_id=access_key_id,aws_secret_access_key=secret_access_key,region_name=region)
            
        response = iot_client.delete_thing(
        thingName= thingName
        )
        return True
    except ClientError as e:
            logging.error(e)
            return False

def det_iotpolicy(thingName, policyId, certArn, region):
    ''' Detach iot Policy on AWS Iot Core
        :param thingName: AWS IoT Thing name to delete
        :param region: AWS region where thing was created
        :param policyId: Iot Policy ID
        :param certArn: IoT certificate ARN
        :return: True if successfully deleted, False if error occurs
    '''
    try: 
        iot_client = boto3.client('iot', aws_access_key_id=access_key_id,aws_secret_access_key=secret_access_key,region_name=region)
              
        response = iot_client.detach_thing_principal(
            thingName=thingName,
            principal=certArn
        )
        
        # Detach Policy from Certificate
        response = iot_client.detach_policy(
            policyName = policyId,
            target = certArn
        )
        return True
    except ClientError as e:
            logging.error(e)
            return False
def del_iotpolicy(policyId, region):
    ''' Delete iot Policy on AWS Iot Core
        :param region: AWS region where thing was created
        :param policyId: Iot Policy ID
        :return: True if successfully deleted, False if error occurs
    '''
    try: 
        if region is None:
            iot_client = boto3.client('iot', aws_access_key_id=access_key_id,aws_secret_access_key=secret_access_key)
        else:
            iot_client = boto3.client('iot', aws_access_key_id=access_key_id,aws_secret_access_key=secret_access_key,region_name=region)
            
        response = iot_client.delete_policy(
        policyName = policyId
        )
        return True
    except ClientError as e:
            logging.error(e)
            return False
            
def del_iotcert(certId, region):
    ''' Delete iot certificate on AWS Iot Core
        :param region: AWS region where thing was created
        :param certId: Iot certificate ID
        :return: True if successfully deleted, False if error occurs
    '''
    try: 
        if region is None:
            iot_client = boto3.client('iot', aws_access_key_id=access_key_id,aws_secret_access_key=secret_access_key)
        else:
            iot_client = boto3.client('iot', aws_access_key_id=access_key_id,aws_secret_access_key=secret_access_key,region_name=region)
        
        # Change certificate status to INACTIVE before it can be deleted
        response = iot_client.update_certificate(
            certificateId=certId,
            newStatus='INACTIVE'
        )
        # Delete certificate
        response = iot_client.delete_certificate(
            certificateId=certId,
            forceDelete=True
        )
        return True
    except ClientError as e:
            logging.error(e)
            return False

def del_iotfiles(filename):
    ''' Delete local certificate files
        :param filename: certificate file to be deleted
        :return: True if successfully deleted, False if error occurs
    '''
    # check if file exists and delete it
    if os.path.isfile(filename):
        print ("File " + filename + " exists, deleting it")
        os.remove(filename)
        return True
    else:
        print(Fore.YELLOW + "File " + filename + " does not exist. Delete skipped!" + Style.RESET_ALL)
        return False
        
if __name__ == '__main__':
    
    # initialize variables

    stackId = None
    codeBucket = None
    rekognitionBucket = None
    policyId = None
    certArn = None
    thingName = None
    publicCertFile = None
    privateCertFile = None
    certFile = None
    
    st_response = None
    cbf_response = None
    cbb_response = None
    
    thing_response = None
    policy_response = None
    cert_response = None

    confirm = input("Do you really want to delete all cloud ressources? ")
    
    if confirm.lower() in ['y', 'yes']:
        # check if cloud parameter file exists
        if os.path.isfile(cloudFile):
            print (Fore.GREEN + "Cloud Parameter file exists" + Style.RESET_ALL)
            my_dict = {}

            # open file and load as JSON
            with open(cloudFile) as f:
                my_dict = json.load(f)
                f.close()

            if 'stack_id' in my_dict:
                stackId = my_dict["stack_id"]
                print("StackID: " + stackId)
            if 'code_bucket' in my_dict:
                codeBucket = my_dict["code_bucket"]
                print("Code Bucket: " + codeBucket)
            if 'region' in my_dict:
                region = my_dict["region"]
                print("Region: " + region)
            if 'rekognition_bucket' in my_dict:
                rekognitionBucket = my_dict["rekognition_bucket"]
                print("Rekognition Bucket " + rekognitionBucket)

            # Clean up Stack and S3 Buckets   
            if codeBucket is not None:

                cbf_response = del_s3files(codeBucket)

                if cbf_response is not False:
                    print(Fore.GREEN + "S3 Files on " + codeBucket + " deleted successfully!" + Style.RESET_ALL)
                else:
                    print(Fore.RED + "S3 files delete on " + codeBucket + " failed!" + Style.RESET_ALL)

                cbb_response = del_s3bucket(codeBucket, region)

                if cbb_response is not False:
                    print(Fore.GREEN + "S3 Bucket "+ codeBucket + " deleted successfully!" + Style.RESET_ALL)
                else:
                    print(Fore.RED + "S3 Bucket " + codeBucket + " delete failed!" + Style.RESET_ALL)
            else:
                print(Fore.RED + "Code Bucket not found!" + Style.RESET_ALL)

            if rekognitionBucket is not None:
                rbf_response = del_s3files(rekognitionBucket)

                if rbf_response is not False:
                    print(Fore.GREEN + "S3 Files on " + rekognitionBucket + " deleted successfully!" + Style.RESET_ALL)
                else:
                    print(Fore.RED + "S3 files delete on " + rekognitionBucket + " failed!" + Style.RESET_ALL)
            if stackId is not None:
                st_response = del_cfstack(stackId, region)
                
                #print("st_response" + str(st_response))
            else:
                print(Fore.RED + "Stack ID not found!" + Style.RESET_ALL)
        else:
            print (Fore.RED + "Cloud parameter file does not exist" + Style.RESET_ALL)
        

        
        # Check if all operations were successful
        if st_response and cbf_response and cbb_response is not False:
            print(Fore.GREEN + "All Stack resources deleted successfully!" + Style.RESET_ALL)
        else:
            print(Fore.RED + "Not all Stack resources have been deleted!" + Style.RESET_ALL)

        # Check if IoT parameter file exists    
        if os.path.isfile(iotFile):
            print (Fore.GREEN + "IOT Parameter file exists" + Style.RESET_ALL)
            my_dict = {}

            # Load iot parameter file content
            with open(iotFile) as f:
                my_dict = json.load(f)
                f.close()
            
            if 'policy_id' in my_dict:
                policyId = my_dict["policy_id"]
                print("Policy ARN: " + policyId)
            if 'certificate_arn' in my_dict:
                certArn = my_dict["certificate_arn"]
                print("Certificate ARN: " + certArn)
            if 'thing_name' in my_dict:
                thingName = my_dict["thing_name"]
                print("Thing Name: " + thingName)
            if 'public_cert_file' in my_dict:
                publicCertFile = my_dict["public_cert_file"]
                print("Public certificate file name: " + publicCertFile)
            if 'private_cert_file' in my_dict:
                privateCertFile = my_dict["private_cert_file"]
                print("Private certificate file name: " + privateCertFile)
            if 'cert_file' in my_dict:
                certFile = my_dict["cert_file"]
                print("Certificate file name: " + certFile)
            if 'region' in my_dict:
                region = my_dict["region"]
                print("IoT Region: " + region)
            
            # Clean up Iot resources    

            if policyId is not None:
                det_iotpolicy(thingName, policyId, certArn, region)
                policy_response = del_iotpolicy(policyId, region)
                
                #print("policy_response" + str(policy_response))

            if certArn is not None:
                pattern = "arn:aws:iot:.*:.*:cert/(.*)"
                match = re.search(pattern, certArn)
                certId = match.group(1)
                print("Cert ID:" + str(certId))
                cert_response = del_iotcert(certId, region)
                
                #print("cert_response" + str(cert_response))
                
            if thingName is not None:
                
                thing_response = del_iotthing(thingName, region)
                
                #print("thing_response" + str(thing_response))
                    
            if publicCertFile and privateCertFile and certFile is not None:
                for f in publicCertFile,privateCertFile,certFile:
                    del_iotfiles(f)
        
        
        # Check if all operations were successful
        if thing_response and policy_response and cert_response is not False:
            print(Fore.GREEN + "All IoT resources deleted successfully!" + Style.RESET_ALL)
        else:
            print(Fore.RED + "Not all IoT resources have been deleted!" + Style.RESET_ALL)
    else:
        print (Fore.RED + "Delete aborted!" + Style.RESET_ALL)
    