#Create an IOT Thing with Certificates, Public Key, Private Key and IOT Policy for Face Recognition Service
#Attach Policy and Certificate to the IoT Thing and return the endpoint address

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
import re
from colorama import Fore, Back, Style
from colorama import init

# Usage
usageInfo = """Usage:
python create_thing.py -a <APIAccessKey> -s <APISecret> -r <AWSRegion> -n <ThingName>
Type "python init_cloud.py -h" for available options.
"""
# Help info
helpInfo = """-a, --accessKey
	AWS User Access Key
-s, --secret
        AWS User Access Secret
-n, --name
    Name of the thing that shall be created
-r, --region
    AWS Region where the stack and the bucket shall be created, if not specified US-EAST-1 will be taken
-h, --help
	Help information
"""
# File that stores the cloud and iot output parameter
filename = 'iot_parameter.txt'

# Read in command-line parameters
thing_name = ""
access_key_id =""
secret_access_key=""
region = 'us-east-1'

try:
    opts, args = getopt.getopt(sys.argv[1:], "hn:a:s:r:", ["help", "name=","accessKey=","secret=","region="])
    if len(opts) == 0:
        raise getopt.GetoptError("No input parameters!")
    for opt, arg in opts:
        if opt in ("-h", "--help"):
            print(helpInfo)
            exit(0)
        if opt in ("-n", "--name"):
            thing_name = arg
        if opt in ("-a", "--accessKey"):
            access_key_id = arg
        if opt in ("-s", "--secret"):
            secret_access_key = arg
        if opt in ("-r", "--region"):
            region = arg
except getopt.GetoptError:
    print(usageInfo)
    exit(1)

# Missing configuration notification
missingConfiguration = False
if not thing_name:
	print("Missing '-n' or '--name'")
	missingConfiguration = True
if not access_key_id:
    print("Missing '-a' or '--accessKey'")
    missingConfiguration = True
if not secret_access_key:
    print("Missing '-s' or '--secret'")
    missingConfiguration = True
if missingConfiguration:
	exit(2)


def write_file(content, filename):
    f = open(filename,"w+")
    f.write(content)
    f.close()
    
def create_thing(thing_name):
    
    """ Create new IOT Thing in AWS IoT Core
        :param thing_name: name of the Thing
        :param region: AWS Region where the IoT Thing is to be created
        :return: True if successfully created, False if error occurs
    """
    
    try:
        response = iot_client.create_thing(
            thingName=thing_name,
        )
    except ClientError as e:
        error_code = (e.response['Error']['Code'])
        if error_code == 'ResourceAlreadyExistsException':
            print("IoT Thing with same name already exists!")
        else:
            logging.error(e)
        return False
    return True
    
def create_certificates(thing_name):
    """ Create Keys and certificates for the Thing
        store the certificates in local files
        :param thing_name: name of the Thing, used for file certificate file names
        :param region: AWS Region where the certificates are created
        :return: CertificateARN if successfully created, False if error occurs
    """
    try:
        cert_response = iot_client.create_keys_and_certificate(
            setAsActive=True
        )
    except ClientError as e:
        logging.error(e)
        return False
    
    #load response as JSON
    data = json.loads(json.dumps(cert_response, sort_keys=False, indent=4))
    for element in data: 
        if element == 'certificateArn':
            certArn = data['certificateArn']
        elif element == 'keyPair':
            PublicKey = data['keyPair']['PublicKey']
            PrivateKey = data['keyPair']['PrivateKey']
        elif element == 'certificatePem':
            certificatePem = data['certificatePem']
        elif element == 'certificateId':
            certificateId = data['certificateId']
    
    print("Certificate ARN:", certArn)
    
    if PublicKey:
        # Write PublicKey, PrivateKey and Certificate to files
        f = open(thing_name+"_public.txt","w+")
        f.write(PublicKey)
        f.close()
        
        print("Public Key: "+thing_name+"_public.txt")
    
    if PrivateKey:
        f = open(thing_name+"_private.txt","w+")
        f.write(PrivateKey)
        f.close()
        
        print("Private Key: "+thing_name+"_private.txt")
    
    if certificatePem:
        f = open(thing_name+"_cert.txt","w+")
        f.write(certificatePem)
        f.close()
        
        print("Certificate: "+thing_name+"_cert.txt")    
    
    return certArn

def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)

def create_iot_policy(thing_name):
    """ Create IoT Policy
        :param thing_name: name of the Thing, used for file certificate file names
        :param region: AWS Region where the certificates are created
        :return: PolicyName if successfully created, False if error occurs
    """
    awsRegion = region
    
    # Create policy name based on Thing Name
    thingPolicy = thing_name+'_IotPolicy'
    
    # Get AccountID for ARN generation in the IoT policy
    try:
        awsAccount = boto3.client('sts',aws_access_key_id=access_key_id,aws_secret_access_key=secret_access_key,region_name=region).get_caller_identity().get('Account')       
        
        # Create IOT Policy Document with required access for Face Recognition Service 
        # (topics:/rekognition/result and /polly/result)
        policyDocumentStr = '''
            {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Action": [
                            "iot:Publish"
                        ],
                        "Resource": [
                            "arn:aws:iot:%s:%s:topic/rekognition/result",
                            "arn:aws:iot:%s:%s:topic/polly/result"
                        ]
                    },
                    {
                        "Effect": "Allow",
                        "Action": [
                            "iot:Subscribe"
                        ],
                        "Resource": [
                            "arn:aws:iot:%s:%s:topicfilter/rekognition/result",
                            "arn:aws:iot:%s:%s:topicfilter/polly/result"
                        ]
                    },
                    {
                        "Effect": "Allow",
                        "Action": [
                            "iot:Receive"
                        ],
                        "Resource": [
                            "arn:aws:iot:%s:%s:topic/rekognition/result",
                            "arn:aws:iot:%s:%s:topic/polly/result"
                        ]
                    },
                    {
                        "Effect": "Allow",
                        "Action": ["iot:Connect"],
                        "Resource": [
                            "arn:aws:iot:%s:%s:client/sdk-java",
                            "arn:aws:iot:%s:%s:client/basicPubSub",
                            "arn:aws:iot:%s:%s:client/sdk-nodejs-*"
                        ]
                    }
                ]
            }
        '''%(awsRegion, awsAccount, awsRegion, awsAccount, awsRegion, awsAccount,awsRegion, awsAccount, awsRegion, awsAccount, awsRegion, awsAccount,awsRegion, awsAccount, awsRegion, awsAccount, awsRegion, awsAccount)
        pattern = re.compile(r'[\s\r\n]+')
        policyDocumentStr = re.sub(pattern, '', policyDocumentStr)
        
        # Create IOT Policy
        policy_response = iot_client.create_policy(
            policyName = thingPolicy,
            policyDocument = policyDocumentStr
        )
        
        # Response and Error handling and formatting
        if 200 != policy_response['ResponseMetadata']['HTTPStatusCode']:
            eprint(Fore.RED + "ERROR: Unable to 'create_thing_type' " + Style.RESET_ALL)
            sys.exit(1)
        print(Fore.GREEN + "Created new policy '" + policy_response['policyName'] + "'" +
                Style.RESET_ALL)
        return policy_response['policyName']
    
    except ClientError as e:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        eprint(Fore.RED + "ERROR in " + fname + ':' + str(exc_tb.tb_lineno) + ' - ' + e.response['Error']['Code'] + ' - ' + e.response['Error']['Message'] + Style.RESET_ALL)
        sys.exit(1)
        return False
        
def attach_policy_certificate(thing_name, certArn, policyId):
    ''' The certificates and IoT policy will be attached to the IoT Thing
        :param thing_name: name of the Thing
        :param certArn: required to attach the certificate/policy to the Thing
        :param policyId: required to attach the certificate/policy to the Thing
        :return: True if successfully created, False if error occurs
    '''
    try:
        # Attach Certificate to Thing
        response = iot_client.attach_thing_principal(
            thingName=thing_name,
            principal=certArn
        )
        
        # Attach Policy to Certificate
        response = iot_client.attach_policy(
            policyName = policyId,
            target = certArn
        )
        
    except ClientError as e:
        logging.error(e)
        return False
    return True
                          
def get_endpoint_address():
    ''' Get and return the IoT Endpoint Address in ATS format
        used later to connect cient to AWS IoT Core
    '''
    try:
        response = iot_client.describe_endpoint(
            endpointType='iot:Data-ATS'
        )
        
    except ClientError as e:
        logging.error(e)
        return False
    return response['endpointAddress']
#------------------------------------------------------------------------------------------------------
if __name__ == '__main__':
    
    #Create new IoT client, used/referenceed inside functions as well
    try: 
        iot_client = boto3.client('iot', aws_access_key_id=access_key_id,aws_secret_access_key=secret_access_key,region_name=region)        
    except ClientError as e:
            logging.error(e)

    print("Creating new IoT Thing:")       
    #Create new IOT Core Thing
    thingResp = create_thing(thing_name)

    if thingResp is not False:
        print(Fore.GREEN + "SUCCESS" + Style.RESET_ALL)
    else:
        print(Fore.RED + "FAILED" + Style.RESET_ALL)
    
    print("Creating new SSL IoT Certificate:")  

    #Create certificate (return certArn)
    certArn = create_certificates(thing_name)

    if certArn is not False:
        print(Fore.GREEN + "SUCCESS" + Style.RESET_ALL)
    else:
        print(Fore.RED + "FAILED" + Style.RESET_ALL)
    
    print("Creating new IoT Policy:")  

    #Create Iot Policy (returns policyId)
    policyId = create_iot_policy(thing_name)

    if policyId is not False:
        print(Fore.GREEN + "SUCCESS" + Style.RESET_ALL)
    else:
        print(Fore.RED + "FAILED" + Style.RESET_ALL)
    
    print("Attaching Cert and Iot Policy to IoT Thing:")  

    #Attach Policy to Thing and Certificate
    attResp = attach_policy_certificate(thing_name, certArn, policyId)
    
    if attResp is not False:
        print(Fore.GREEN + "SUCCESS" + Style.RESET_ALL)
    else:
        print(Fore.RED + "FAILED" + Style.RESET_ALL) 
    #Get and print the IOT Endpoint address
    print("Your Endpoint Address is:", get_endpoint_address())
    
    output={}

    if thingResp is not False:
        output["thing_name"] = thing_name
        output["region"] = region
    if certArn is not False:
        output["certificate_arn"] = certArn
        output["public_cert_file"] = thing_name + "_public.txt"
        output["private_cert_file"] = thing_name + "_private.txt"
        output["cert_file"] = thing_name + "_cert.txt"
    if policyId is not False:
        output["policy_id"] = policyId

    if output is not False:
        write_file(json.dumps(output), filename)
        print("Output parameters are written to: "+ filename)
    else:
        print("No output paramaters received, skipped writing file!")