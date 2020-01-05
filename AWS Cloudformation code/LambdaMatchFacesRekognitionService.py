# This script is triggered by the upload of a JPG image in the folder /matches on S3
# It compares the picutre against the collection of known faces with AWS FaceRekognition service
# If a match is found it get's the Full Name and the filename for the corresponding MP3 from DynamoDB
# it generates a presigned URL for the MP3 and sends it back in a IOT message to the client for playback
# it sends the results of the face match action also as an IOT response to the client for further actions

from __future__ import print_function

import boto3
from decimal import Decimal
import json
import urllib
import os
import botocore
import datetime
import re
import ast

# Initialize variables from env. variables
collectionName = os.environ["COLLECTION"]
regionName = os.environ["REGION"]
tableName = os.environ["TABLE"]

# Initialize client connections
rekognition = boto3.client('rekognition')
iot = boto3.client('iot-data')
dynamodb = boto3.client('dynamodb', region_name=regionName)

# Define FileName to be used if no match is found
defaultMP3 = 'No_face_match.mp3'

def getPresignedS3Url(bucket, desturl, region):
    # Define URL format based on S3 region
    # Create boto3 S3 client and get the pre-signed URL
    
    try:
        s3 = boto3.client('s3')
        session = boto3.Session()
        s3 = session.client('s3', region_name=region)
        signedUrl = s3.generate_presigned_url(
            ClientMethod="get_object",
            ExpiresIn=600,  # valid for 30 minutes
            HttpMethod='GET',
            Params={
                "Bucket": bucket,
                "Key": desturl,
            }
        )
        print("Signed URL for S3 mp3:")
        print(signedUrl)

        return(signedUrl)
    
    except botocore.exceptions.ClientError as error:
        print("Error Message Output from Exception:")
        print(error.response['Error']['Code'])
        raise error
        return False
        
def publishIotMessage(strtopic, strData):
    # send iot response to specified topic
    
    try:
        iotResponse = iot.publish(
            topic=strtopic,
            qos=1,
            payload=strData)
        return iotResponse
    
    except botocore.exceptions.ClientError as error:
        print("Error Message Output from Exception:")
        print(error.response['Error']['Code'])
        raise error
        return False
#--------------- Helper Functions to call Rekognition APIs ------------------

def default(obj):
    """Default JSON serializer."""
    import calendar, datetime

    if isinstance(obj, datetime.datetime):
        if obj.utcoffset() is not None:
            obj = obj - obj.utcoffset()
        millis = int(
            calendar.timegm(obj.timetuple()) * 1000 +
            obj.microsecond / 1000
        )
        return millis
    raise TypeError('Not sure how to serialize %s' % (obj,))
#------------------------------------------------------------------------------

def compare_faces(bucket, key, threshold=80):
    try:
        response = rekognition.search_faces_by_image(
            CollectionId=collectionName,
            Image={
                "S3Object": {
                    "Bucket": bucket,
                    "Name": key,
                }
            }
        )
        print("Recognition Response:")
        print(response)
    
    # If no face was detected in the image, return error response
    except botocore.exceptions.ClientError as error:
        print("Error Message Output from Exception:")
        print(error.response['Error']['Code'])
        if error.response['Error']['Code'] == "InvalidParameterException":
            print("Exception in if condition")
            response = '{"Match_found": "No face","Full_name": "n/a"}'
            return response
        else:
            raise error
    
    if not response['FaceMatches']:
        print ('no match found in person lookup')
        # Create artificial response for no face match
        faceItem = json.dumps({'Match_found': 'false', 'Full_name': 'none'})
        print(faceItem)
    else:
        # Get person details from DynamoDB by matching with the FaceID as primary key (RekognitionId)
        for match in response['FaceMatches']:
            print (match['Face']['FaceId'],match['Face']['Confidence'])
            face = dynamodb.get_item(TableName=tableName,Key={'RekognitionId': {'S': match['Face']['FaceId']}})
            print("Response from DynamoDB query:")
            print(face)
            if 'Item' in face:
                faceItem = json.dumps({'Match_found': 'true', 'Full_name': face['Item']['FullName']['S'], 'File_name': face['Item']['FileName']['S']})
                
                print("Face Item:")
                print(faceItem)
    return faceItem

# --------------- Main handler ------------------


def lambda_handler(event, context):
    print("Received event: " + json.dumps(event, indent=2))
    
    #Get S3 Bucket name from event
    bucket = event['Records'][0]['s3']['bucket']['name']
    
    #Get S3 Key name from event
    key = urllib.unquote_plus(event['Records'][0]['s3']['object']['key'].encode('utf8'))
    print(key)

    try: 
        s3 = boto3.client('s3')
        # HEAD to S3 object to get Metadata (recid) in response
        s3response = s3.head_object(Bucket=bucket, Key=key)
        
        # format HTTP response
        s3JsonResponse = json.dumps(s3response, default=default)
        s3JsonResponse = s3JsonResponse.encode("ascii","replace") 
        
        # extract recid with regex search
        matchObj = re.search(r'"recid": "(\d*)".*', s3JsonResponse)
        if matchObj:
            recid = matchObj.group(1)
            print("RecID found:" + recid)
        else:
            print ("No RecID found!!")
    
    # throw excpetion if this fails
    except botocore.exceptions.ClientError as e:
        if e.response['Error']['Code'] == "404":
            print("The object does not exist.")
        else:
            raise
    
    try:
        # compare faces
        response = compare_faces(bucket, key)
        print("Compare_Faces response:")
        print(response)
        
        # convert string to dict for direct access to elements and modification
        response = ast.literal_eval(response)
        
        # add RecID to the face match response for IOT message to the client
        print("RecID for Payload")
        print(recid)
        response['Recid'] = recid
        print("Iot message payload:")
        print(response)
        
        # convert dict/json back to string before sending as payload
        strResponse = json.dumps(response)
        print("Iot message payload as string:")
        print(strResponse)
        
        # send iot response with recognition results
        
        iotResponse = publishIotMessage("rekognition/result", strResponse)
        print("IOT Publish response for rekognition/result topic:")
        print (iotResponse)
        
        # get MP3 name from Dynamo DB with FaceID
        # fallback to no_match_mp3 if no match was found
        # generate S3 Presigned URL
        # send url in IOT response

        # If a face match was found use the "File_name" we got from DynamoDB entry 
        if response['Match_found'] not in "false":
            
            mp3FileName = response['File_name'] 
        # If no face match was found, use the default MP3 filename
        else:
            mp3FileName = defaultMP3
        
        s3url = getPresignedS3Url(bucket, "mp3/"+mp3FileName, regionName)
        
        if s3url is not False:
            # create iot response data with S3 url and recid
            data = {}
            data['s3url'] = s3url
            data['recid'] = recid
            strData = json.dumps(data)
            
            # Publish the response data to Iot topic polly/result
            iotResponse = publishIotMessage("polly/result", strData)
            print("IOT Publish response for polly/result topic:")
            print (iotResponse)
        
        else:
            print("Error occured: S3 URL cannot be generated!")
            
        try:
            response = s3.delete_object(Bucket=bucket, Key=key)
        except Exception as e:
            print(e)
            raise e
    except Exception as e:
        print(e)
        raise e