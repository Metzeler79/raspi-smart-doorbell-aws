# This script is triggered by an upload of a JPG file to the folder /index on S3
# It triggers AWS Face Rekongnition to create a new index in the collection for the new face
# If this is successful it creates a new entry in DynamoDB together with the Full Name (extracted from S3 Metadata for the file)
# and the filename for the MP3 file that shall be used for this user
# it further generates a SNS message that triggers the "LambdaGenerateVoiceMsgWithPolly" function, which generates the MP3 file and stores it on S3

from __future__ import print_function

import boto3
from decimal import Decimal
import json
import urllib
import os

# Initialize Clients
dynamodb = boto3.client('dynamodb')
s3 = boto3.client('s3')
rekognition = boto3.client('rekognition')
sns = boto3.client('sns')

# Initialize Enviroment Variables
tableName = os.environ["TABLE"]
collectionName = os.environ["COLLECTION"]
snsArn = os.environ["SNS_TOPIC_ARN"] 

# --------------- Helper Functions ------------------
# Triggers a new index for a face with AWS Rekognition
def index_faces(bucket, key):
    response = rekognition.index_faces(
    Image={"S3Object":
      {"Bucket": bucket,
      "Name": key}},
        CollectionId=collectionName)
    return response

# Updates DynamoDB entries for known users
def update_index(tableName,faceId, fullName, fileName):
    response = dynamodb.put_item(
    TableName= tableName,
    Item={
      'RekognitionId': {'S': faceId},
      'FullName': {'S': fullName},
      'FileName': {'S': fileName}
      }
  )
    return response

# --------------- Main handler ------------------

def lambda_handler(event, context):
    # Get the object from the event
    bucket = event['Records'][0]['s3']['bucket']['name']
    key = urllib.unquote_plus(
    event['Records'][0]['s3']['object']['key'].encode('utf8'))
    
    print("S3 Key:"+key)
    try:
        # Calls Amazon Rekognition IndexFaces API to detect faces in S3 object
        # to index faces into specified collection
        response = index_faces(bucket, key)
        
        # Commit faceId and full name object metadata to DynamoDB
        if response['ResponseMetadata']['HTTPStatusCode'] == 200:
            
            faceId = response['FaceRecords'][0]['Face']['FaceId']
            print("FaceId:")
            print(faceId)
            # Define Filename for Mp3 (<faceid>.mp3)
            
            fileName = faceId+'.mp3'
            # Head S3 object and extract the Full Name from the object metadata (was sent in x-amz-meta-fullname header during upload to S3)
            ret = s3.head_object(Bucket=bucket,Key=key)
            fullName = ret['Metadata']['fullname']
            
            print("S3 response for HEAD:")
            print(ret)
            print("Fullname extracted:")
            print(fullName)
            
            # create DynamoDB entry for new Face
            response = update_index(tableName,faceId,fullName, fileName)
            
            # Print response to console.
            print("Update Dynamo DB response:")
            print(response)
            
            # Define the text here that is used for the MP3 file
            defaultText = 'Hey ' + fullName + '! Come in homie! Grab a beer and relax!'
            
            # Generate content for SNS Message, needs Filename and Text to synthesize
            snsmsg={}
            snsmsg['File_name'] = fileName
            snsmsg['Text'] = defaultText

            # convert dict/json back to string before sending as payload
            strResponse = json.dumps(snsmsg)
            print("strResponse:")
            print(strResponse)
            
            # Publish message to the specified SNS topic
            sns_response = sns.publish(
                TopicArn=snsArn,    
                Message=strResponse,
            )
            print("SNS Response:")
            print(sns_response)
            
            # delete image on S3
            try:
                response = s3.delete_object(Bucket=bucket, Key=key)
                
                # Print response to console
                print("Deleted image "+key+" from /index")
                print("S3 reponse:")
                print(response)
                
            except Exception as e:
                print(e)
                raise e
        
        return response
    except Exception as e:
        print(e)
        print("Error processing {} from bucket {}. ".format(key, bucket)) 
        raise e