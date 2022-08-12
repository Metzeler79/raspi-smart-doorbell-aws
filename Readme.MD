# Raspberry Pi smart doorbell project

## Overview

This little project builds a smart doorbell. Smart features include face recognition and playing a personalized greeting message on a speaker. The design uses several AWS cloud services which can be provisioned with a Cloudformation template quickly.

I started with this project in order to play around with different AWS services, especially IoT, Cloudformation and Lambda in a simulated real world scenrario based on Raspberry Pi.

AWS Services used in this project:

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
- Electronic components (LEDs, resistors etc.) as shown in the circuit plan (incl. breadboard)
- Raspberry Pi compatible camera module
- Speaker with 3.5 mm audio jack
- AWS API credentials with corresponding access rights

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
- Picamera 
    ```Shell
    Installation see:
    https://picamera.readthedocs.io/en/release-1.10/install3.html
    ```
## Workflow

Note: Register at least one picture (known person) with the AWS Face Rekognition service before starting the smartdoor.py script.
Registering/provisioning is done by the script smartdoor_new_face.py.

1. Start the smartdoor.py script
2. Push the button on the breadboard circuit (buzzer makes some noise (i.e. "Bell rings"), LCD panel shows that a photo has to be taken and counts back from 3 to 1).
3. Yellow LED = ON, camera takes a picture and the script uploads the JPG to AWS S3 which triggers the cloud workflow to detect if the person in this picture is known and allowed to open the door or not
4. Depending on the result of the rekognition workflow 

   Detection successful:

   -> Green LED = ON (simulates that the door is open), LCD Panel shows the name of the detected person, personal greeting message is played on the speaker
   
   Detection unsuccessful:

   -> Red LED = ON (simulates that the door remains locked), LCD Panel shows unsuccessful detection, default audio message for unknown persons is played on the speaker.

## Circuit

see /Raspberry breadboard circuit layout/Raspi_Circuit_Layout.pdf

## AWS Cloud Architecture

see /Architecture/SmartDoorbell_AWS.pdf

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

The script creates a file called "cloud_parameter.txt" that contains the details about the created AWS cloud resources. This file needs to be retained if you want to use the "delete_cloud.py" script later to automatically clean up all cloud resources.

### create_thing.py

This script should be executed after cloud_init.py script. It creates a new "IoT thing" in AWS IoT Core service with all necessary IoT policies and stores the corresponding client certificates on the Raspberry Pi.

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

The script creates a file called "iot_parameter.txt" that contains the details about the created AWS IoT resources. This file needs to be retained if you want to use the "delete_cloud.py" script later to automatically clean up all IoT resources.

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

Registers/Provision a new person/face in AWS Rekognition service. The person will be detected as authorized, which allows to open the door.

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

This script runs the smart door bell service on the Raspberry Pi and interacts with the circuit and the AWS Cloud/IoT ressources.
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

Lambda function code (Lambda functions are created by the AWS cloudformation template automatically):

- LambdaGenerateVoiceMsgWithPolly.zip -> contains LambdaGenerateVoiceMsgWithPolly.py

    Generates the audio files with AWS Polly and stores them in an S3 bucket.

- LambdaIndexFaces.zip -> contains LambdaIndexFaces.py

    Registers new persons/faces in the AWS Rekognition service and stores the person's details (name, Rekognition ID, greeting message URL) in DynamoDB. 
    This scirpt also triggers LambdaGenerateVoiceMsgWithPolly.py via SNS.

- LambdaMatchFacesRekognitionService.py

    Face rekognition service that matches images against a database of known users. The result is published to an IoT topic to which the Raspberry Pi subscribes.

- cf_FaceRekognitionService_V1.2.0.yaml

    Cloudformation template that defines the AWS ressources required for the smart door bell service.

## Remark

Some parts of the code for this project are inspired by: https://softwaremill.com/access-control-system-with-rfid-and-amazon-rekognition/
