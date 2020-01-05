# Smartdoor PoC that uses AWS Rekognition, S3, DynamoDB, Polly and IoT Core to simulate a 
# door that uses face rekognition to detect authorized persons that are allowed to come in
# The code for this project is inspired and based on: https://softwaremill.com/access-control-system-with-rfid-and-amazon-rekognition/
from AWSIoTPythonSDK.MQTTLib import AWSIoTMQTTClient
import sys
import logging
import time
import getopt
from datetime import datetime
import picamera
import os
import boto3
import json
import random
import RPi.GPIO as GPIO
import urllib.request, urllib.error, urllib.parse
import pygame
from PCF8574 import PCF8574_GPIO
from Adafruit_LCD1602 import Adafruit_CharLCD
import serial
import time
from botocore.exceptions import ClientError

# Usage
usageInfo = """Usage:
Use certificate based mutual authentication:
python smartdoor.py -e <endpoint> -r <rootCAFilePath> -c <certFilePath> -k <privateKeyFilePath> -a <APIAccessKey> -s <APISecret> -b <Bucketname>
Type "python smartdoor.py -h" for available options.
"""
# Help info
helpInfo = """-e, --endpoint
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
"""

# Read in command-line parameters
host = ""
rootCAPath = ""
certificatePath = ""
privateKeyPath = ""
access_key_id =""
secret_access_key=""
bucket_name=""

try:
	opts, args = getopt.getopt(sys.argv[1:], "hwe:k:c:r:a:s:b:", ["help", "endpoint=", "key=","cert=","rootCA=","accessKey=","secret=","bucket="])
	if len(opts) == 0:
		raise getopt.GetoptError("No input parameters!")
	for opt, arg in opts:
		if opt in ("-h", "--help"):
			print(helpInfo)
			exit(0)
		if opt in ("-e", "--endpoint"):
			host = arg
		if opt in ("-r", "--rootCA"):
			rootCAPath = arg
		if opt in ("-c", "--cert"):
			certificatePath = arg
		if opt in ("-k", "--key"):
			privateKeyPath = arg
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
if not host:
	print("Missing '-e' or '--endpoint'")
	missingConfiguration = True
if not rootCAPath:
	print("Missing '-r' or '--rootCA'")
	missingConfiguration = True
if not certificatePath:
    print("Missing '-c' or '--cert'")
    missingConfiguration = True
if not privateKeyPath:
    print("Missing '-k' or '--key'")
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

# Configure logging
logger = logging.getLogger("AWSIoTPythonSDK.core")
logger.setLevel(logging.DEBUG)
streamHandler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
streamHandler.setFormatter(formatter)
logger.addHandler(streamHandler)

# Init AWSIoTMQTTClient
myAWSIoTMQTTClient = None

myAWSIoTMQTTClient = AWSIoTMQTTClient("basicPubSub")
myAWSIoTMQTTClient.configureEndpoint(host, 8883)
myAWSIoTMQTTClient.configureCredentials(rootCAPath, privateKeyPath, certificatePath)

# AWSIoTMQTTClient connection configuration
myAWSIoTMQTTClient.configureAutoReconnectBackoffTime(1, 32, 20)
myAWSIoTMQTTClient.configureOfflinePublishQueueing(-1)  # Infinite offline Publish queueing
myAWSIoTMQTTClient.configureDrainingFrequency(2)  # Draining: 2 Hz
myAWSIoTMQTTClient.configureConnectDisconnectTimeout(10)  # 10 sec
myAWSIoTMQTTClient.configureMQTTOperationTimeout(5)  # 5 sec

# camera setup
camera = picamera.PiCamera()
camera.resolution = (image_width, image_height)
camera.awb_mode = 'auto'

buzzerPin = 11    # define the buzzerPin
buttonPin = 12    # define the buttonPin
redLedPin = 16    # define red led pin
grnLedPin = 22    # define green led pin
ylwLedPin = 18    # define yellow led pin

PCF8574_address = 0x27  # I2C address of the PCF8574 chip.
PCF8574A_address = 0x3F  # I2C address of the PCF8574A chip.
# Create PCF8574 GPIO adapter.
try:
	mcp = PCF8574_GPIO(PCF8574_address)
except:
	try:
		mcp = PCF8574_GPIO(PCF8574A_address)
	except:
		print ('I2C Address Error !')
		exit(1)
# Create LCD, passing in MCP GPIO adapter.
lcd = Adafruit_CharLCD(pin_rs=0, pin_e=2, pins_db=[4,5,6,7], GPIO=mcp)

# Counter for retries if no face is detected
noFaceCounter = 0

#--------------------------------- GPIO Functions --------------------------------------------
def setup():
    GPIO.setmode(GPIO.BOARD)       # Numbers GPIOs by physical location
    GPIO.setup(buzzerPin, GPIO.OUT)   # Set buzzerPin's mode is output
    GPIO.setup(buttonPin, GPIO.IN, pull_up_down=GPIO.PUD_UP)    # Set buttonPin's mode is input, and pull up to high level(3.3V)
    GPIO.setup(redLedPin, GPIO.OUT)
    GPIO.setup(grnLedPin, GPIO.OUT)
    GPIO.setup(ylwLedPin, GPIO.OUT)
    
def destroy():
    GPIO.output(buzzerPin, GPIO.LOW)     # buzzer off
    GPIO.cleanup()                     # Release resource
    lcd.clear()

#--------------------------------- Helper Functions --------------------------------------------
def randomDigits(digits):
    lower = 10**(digits-1)
    upper = 10**digits - 1
    return random.randint(lower, upper)
        
def uploadToS3(file_name):
    
    filepath = file_name + file_extension
    camera.capture(filepath)
    try:
        client = boto3.client('s3',aws_access_key_id=access_key_id,aws_secret_access_key=secret_access_key)
        response = client.upload_file(filepath, bucket_name, "matches/" + filepath,ExtraArgs={'Metadata': {'cache-control': 'max-age=60','recid': file_name}})
    except ClientError as e:
        logging.error(e)
        return False
    return True

    if os.path.exists(filepath):
        os.remove(filepath)
        
#--------------------------------- IOT Callback Functions --------------------------------------------
def pollyCallback(client, userdata, message):

    print("Received a new message: ")
    data = json.loads(message.payload.decode('utf-8'))
    try:
        # extract URL + RecID
        s3url = data['s3url']
        print(("Received s3url: " + str(s3url)))
        
        rcvid = data['recid']
        print(("Received RecID: " + str(rcvid)))
        
        # compare RecID to local one and play message     
        if str(recid) == str(rcvid):       
            print("Download S3 URL")
            filedata = urllib.request.urlopen(s3url)
            datatowrite = filedata.read()
            
            print("write Data to local File")
            filename = rcvid + ".mp3"
            with open(filename, 'wb') as f:
                f.write(datatowrite)
        
            pygame.mixer.pre_init(44100, -16, 2, 2048) # setup mixer to avoid sound lag
            pygame.init()
            pygame.mixer.init()
            pygame.mixer.music.load(filename)
            print ("play")
            pygame.mixer.music.play()
            
            # Delete MP3 File
            if os.path.exists(filename):
                os.remove(filename)

        else:
            print("RecID does not match")
            return
        
        global locked
        locked = 0
        
    except Exception as e:
        print(e)
        raise e
        
def photoVerificationCallback(client, userdata, message):
    
    global noFaceCounter

    print("Received a new message: ")
    data = json.loads(message.payload.decode('utf-8'))
    print(data)
    try:
        match = data['Match_found']
        print(("Received match: " + str(match)))
        fullname = data['Full_name']
        print(("Received Name: " + str(fullname)))
        rcvid = data['Recid']
        print(("Received RecID: " + str(rcvid)))
        
        # compare RecID to local one and play message     
        if str(recid) == str(rcvid):    
            if match == "false":
                
                # reset noFaceCounter
                noFaceCounter = 0

                print("No Match found!")
                lcd.clear()
                #lcd.setCursor(0,0)  # set cursor position
                lcd.message( 'I don`t know' )
                lcd.setCursor(0,1)
                lcd.message( 'you. Go away!' )
                #time.sleep (5)

                # change LED Light from yellow to red
                GPIO.output(ylwLedPin,GPIO.LOW) # deactivate yellow LED
                GPIO.output(redLedPin,GPIO.HIGH) # activate red LED
                GPIO.output(grnLedPin,GPIO.LOW) # deactivate green LED
                
                # Reset locked variable
                global locked
                locked = 0

            elif match == "No face":
                if noFaceCounter < 3:
                    noFaceCounter = noFaceCounter + 1
                    print("No Face in image decteted, lets try again")
                    lcd.clear()
                    lcd.message('No face detetect')
                    lcd.setCursor(0,1)
                    lcd.message('in image.')
                    time.sleep(2)

                    for x in range(3, 0,-1):
                        lcd.clear()
                        lcd.message("Photo in %d" %x)
                        time.sleep(0.5)

                    lcd.setCursor(0,1)
                    lcd.message('Cheese! :-)')
                    print("taking photo....")
                    uploadToS3(recid)
                else:
                    noFaceCounter = 0
                    locked = 0

                    # Reset LEDs and LCD Display
                    initHardware()
                    return
            else:
                print("Match found!")

                # reset noFaceCounter
                noFaceCounter = 0

                lcd.clear()
                lcd.message( fullname )# 
                lcd.setCursor(0,1) 
                lcd.message( 'Come in!')# 

                # change LED Light from yellow to green
                GPIO.output(ylwLedPin,GPIO.LOW) # deactivate yellow LED
                GPIO.output(grnLedPin,GPIO.HIGH) # activate green LED
                GPIO.output(redLedPin,GPIO.LOW) # deactivate red LED
                
        else:
            print("RecID does not match")
            return
    except:
        pass
    print("Finished processing event.")

#--------------------------------- Main Loop --------------------------------------------
def buttonEvent(channel):
    
    global locked
    
    if locked == 0: 
        
        locked = 1
        
        GPIO.output(ylwLedPin,GPIO.LOW) # deactivate yellow LED
        GPIO.output(grnLedPin,GPIO.LOW) # deactivate green LED
        GPIO.output(redLedPin,GPIO.LOW) # deactivate red LED
        
        lcd.clear()
        lcd.message('Let`s go!')

        # Buzzer on
        print('buzzer on ...')
        GPIO.output(buzzerPin,GPIO.HIGH)
        time.sleep(2)
        # Buzzer off
        GPIO.output(buzzerPin,GPIO.LOW)
        
        lcd.clear() # clear LCD
        
        # create random recognition id
        global recid 
        recid = str(randomDigits(15))
        
        # activate yellow LED
        GPIO.output(ylwLedPin,GPIO.HIGH)
        
        lcd.message('Let`s check who')
        lcd.setCursor(0,1)
        lcd.message('you are...')
        time.sleep(1.5)
        
        for x in range(3, 0,-1):
            lcd.clear()
            lcd.message("Photo in %d" %x)
            time.sleep(0.5)
            
        lcd.setCursor(0,1)
        lcd.message('Cheese! :-)')
        print("taking photo....")
        uploadToS3(recid)
        
    else:
        print("Button pushed")
            
def loop():
    #Button detect
    GPIO.add_event_detect(buttonPin,GPIO.FALLING,callback = buttonEvent,bouncetime=800)
    while True:
        time.sleep(0.05)
        pass

def initHardware():
        mcp.output(3,1)     # turn on LCD backlight
        lcd.begin(16,2)     # set number of LCD lines and column
        GPIO.output(ylwLedPin,GPIO.LOW) # turn off all LEDs
        GPIO.output(redLedPin,GPIO.LOW) # turn off all LEDs
        GPIO.output(grnLedPin,GPIO.LOW) # turn off all LEDs
        lcd.clear() # clear LCD
#--------------------------------- Main function --------------------------------------------
if __name__ == '__main__':
    setup()
    try:
        # Initialize LEDs and LCD display
        initHardware()

        # Connect and subscribe to AWS Iot
        myAWSIoTMQTTClient.connect()
        myAWSIoTMQTTClient.subscribe("rekognition/result", 1, photoVerificationCallback)
        time.sleep(1)
        myAWSIoTMQTTClient.subscribe("polly/result", 1, pollyCallback)
        time.sleep(1)
        
        locked = 0
        
        loop()
        
    except KeyboardInterrupt:  # When 'Ctrl+C' is pressed, the child program destroy() will be  executed.
        destroy()