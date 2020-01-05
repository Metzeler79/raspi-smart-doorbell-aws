# This script is triggered by an SNS notification which contains a filename and a text
# Script triggers AWS Polly to synthesize the text to speech and store the resulting MP3 with the filename from SNS Message on S3

import boto3
import os
from contextlib import closing
import json
import ast

def lambda_handler(event, context):
    
    bucket = os.environ['BUCKET_NAME']
    
    # Get Message content from SNS
    message = event['Records'][0]['Sns']['Message']
    print("SNS Message received:" + message)

    # convert string to dict for direct access to elements and modification
    message = ast.literal_eval(message)
    
    # Get Filename, Text from SNS
    fileName = message["File_name"]
    text = message["Text"]
    
    print "Filename: " + fileName
    print "Text: " + text

    #invoke Polly API, which will transform text into audio
    polly = boto3.client('polly')
    response = polly.synthesize_speech(
        OutputFormat='mp3',
        Text = text,
        VoiceId = 'Joey'
    )
    
    if "AudioStream" in response:
        with closing(response["AudioStream"]) as stream:
            output = os.path.join("/tmp/", fileName)
            with open(output, "a") as file:
                file.write(stream.read())
                
    # Upload the result from Polly Text-to-Speech to S3
    print("Continuing with S3 Upload")
    
    # define S3 paramaters
    source = '/tmp/' + fileName
    desturl = "mp3/" + fileName
    
    # create S3 client
    s3 = boto3.client('s3')
    
    # Get the region for the bucket in order to determine the right URL format for S3 Object later
    location = s3.get_bucket_location(Bucket=bucket)
    region = location['LocationConstraint']
    print ("S3 region:")
    print(region)

    # Upload Polly file to S3
    s3.upload_file(source, 
                   bucket, 
                   desturl)
    
    return