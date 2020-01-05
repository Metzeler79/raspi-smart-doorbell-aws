# Raspberry Pi Smart doorbell project
## Disclaimer

The code for this project is inspired and based on: https://softwaremill.com/access-control-system-with-rfid-and-amazon-rekognition/

## Overview

This little project simulates a smart doorbell. The smart functions are face detection when someone rings the bell and playing an individual audio file for each known person (and a default audio message if the user is unknown). The service involves several AWS cloud services which can be provisioned with a Cloudformation template quickly.

I started with this project in order to play around with different AWS services, especially IoT, Cloudformation and Lambda in a simulated real world scenrario based on Raspberry Pi.

AWS Services that are used:

- AWS S3
- AWS SNS
- AWS Rekognition
- AWS Polly
- AWS Lambda
- AWS DynamoDB
- AWS IoT Core
- AWS Cloud Formation

## Requirements

Hardware:

- Raspberry Pi 3 or newer model with Raspbian OS
- electronic components as shown in the circuit plan (incl. breadboard)
- Raspberry pi compatible camera module
- speaker with 3.5 mm audio jack
- AWS API credentials (admin access rights recommended)

Software:

- Python3
- Pip
- AWS boto 3 client
    ```Shell
    pip install boto3
    ```

- AWS IoT Device SDK for Python
    ```Shell
    cd ~
    git clone https://github.com/aws/aws-iot-device-sdk-python.git
    cd aws-iot-device-sdk-python
    sudo python setup.py install

    pip install AWSIoTPythonSDK
    ```

- Colorama Module
    ```Shell
    pip install colorama
    ```
## Workflow

Note: Register at least one known face with the AWS Face Rekognition service before playing with the workflow (registering possible with script smartdoor_new_face.py).

1. Push the button on the circuit (buzzer makes some noise ("Bell rings"), LCD panel informs that a photo needs to be taken and counts back from 3 to 1)
2. Yellow LED = ON, Camera takes a picture and the script uploads the JPG to AWS S3 which triggers the cloud workflow to detect if the person is known and allowed to access or not
3. Depending on the result of the rekognition workflow 

   Detection successful:

   -> Green LED = ON (simulates that door is opened), LCD Panel shows the name of the detected person, personal audio message is played on the speaker
   
   Detection unsuccessful:

   -> Red LED = ON (simulates that door stays locked), LCD Panel informs about unsuccessful detection, default audio message for unknown persons is played on the speaker.

## Circuit

see Circuitdesign.pdf

## AWS Cloud Architecture

see SmartDoorbell_AWS.pdf

## Scripts

### cloud_init.py

This script should be executed first. It creates all required AWS resources with AWS Cloudformation service.
```Shell
Parameter:

-a, --accessKey
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
```
```Shell
Usage:

python init_cloud.py -p <codePath> -a <APIAccessKey> -s <APISecret> -b <Bucketname> -r <AWSRegion>
```

Remark: If no region is specified, the AWS resources will be created in US-EAST-1 region.

The script creates a file called "cloud_parameter.txt" that contains the details for the AWS cloud resources that have been created. This file needs to be retained if you want to use the "delete_cloud.py" script later to automatically delete all cloud resources.

### create_thing.py

This script should be executed after cloud_init.py script. It creates a new IoT Thing in AWS IoT Core service with all necessary IoT policies and stores the corresponding client certificates on the Raspberry Pi.

```Shell
Parameter:

-a, --accessKey
	AWS User Access Key
-s, --secret
        AWS User Access Secret
-n, --name
    Name of the thing that shall be created
-r, --region
    AWS Region where the stack and the bucket shall be created, if not specified US-EAST-1 will be taken
-h, --help
	Help information
```
```Shell
Usage:
python create_thing.py -a <APIAccessKey> -s <APISecret> -r <AWSRegion> -n <ThingName>
```
Remark: If no region is specified, the AWS resources will be created in US-EAST-1 region.

The script creates a file called "iot_parameter.txt" that contains the details for the AWS IoT resources that have been created. This file needs to be retained if you want to use the "delete_cloud.py" script later to automatically delete all IoT resources.

### delete_cloud.py

Deletes all AWS Cloud and IoT ressources.

Requires that the script is executed from the directory that contains the parameter files that are created by "create_thing.py" and "cloud_init.py". 
```Shell
Parameter:

-a, --accessKey
	AWS User Access Key
-s, --secret
        AWS User Access Secret
-h, --help
	Help information
```
```Shell
Usage: python delete_cloud.py -a <APIAccessKey> -s <APISecret>
```
### smartdoor_new_face.py

Registers a new person/face in AWS Rekognition. The person will be detected as known (or authorized) person when the smart door bell is used, which allows them to access the door.
```Shell
Parameter:

-n, --name
	Name of the new user
-a, --accessKey
	AWS User Access Key
-s, --secret
        AWS User Access Secret
-b, --bucket
        S3 Bucketname that was provisioned for FaceRecognition Service
-h, --help
	Help information

```
```Shell
Usage:
python smartdoor_new_face.py -n <name> -a <APIAccessKey> -s <APISecret> -b <Bucketname>
```
### smartdoor.py

This script implements the smart door bell service and interacts with the circuit and the AWS cloud/IoT ressources.
```Shell
Parameter:
-e, --endpoint
	Your AWS IoT custom endpoint
-r, --rootCA
	Root CA file path
-c, --cert
	Certificate file path
-k, --key
	Private key file path
-a, --accessKey
	AWS User Access Key
-s, --secret
        AWS User Access Secret
-b, --bucket
        S3 Bucketname that was provisioned for FaceRecognition Service
-h, --help
	Help information
```
```Shell
Usage:

python smartdoor.py -e <endpoint> -r <rootCAFilePath> -c <certFilePath> -k <privateKeyFilePath> -a <APIAccessKey> -s <APISecret> -b <Bucketname>
```
## AWS Cloud files

Lambda function code (functions are created by AWS cloudformation automatically with the stack):

- LambdaGenerateVoiceMsgWithPolly.zip -> contains LambdaGenerateVoiceMsgWithPolly.py

    Generates the audio files with AWS Polly and stores then in an S3 bucket.

- LambdaIndexFaces.zip -> contains LambdaIndexFaces.py

    Registers new persons/faces in AWS Rekognition service and stores the details in DynamoDB. Triggers LambdaGenerateVoiceMsgWithPolly.py via SNS.

- LambdaMatchFacesRekognitionService.py

    Face rekognition service that matches images against a DB of known users and sends back the result in IoT topics to the Raspberry Pi.

- cf_FaceRekognitionService_V1.2.0.yaml

    Cloudformation template that defines the AWS ressources required for the Smart door bell service.