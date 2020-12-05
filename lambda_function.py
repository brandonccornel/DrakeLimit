import json
import requests
import spotipy.util as util
import csv
import datetime
from datetime import date
import time
from datetime import timedelta

import os
from twilio.rest import Client
import boto3

s3 = boto3.client('s3')

SPOTIFY_USERNAME = os.environ['SPOTIFY_USERNAME']
SPOTIFY_CLIENT_ID = os.environ['SPOTIFY_CLIENT_ID']
SPOTIFY_CLIENT_SECRET = os.environ['SPOTIFY_CLIENT_SECRET']
SPOTIFY_REDIRECT_URI = 'http://localhost:7777/callback'
SPOTIFY_SCOPE = 'user-read-recently-played'
SPOTIFY_BASE_URL = 'https://api.spotify.com/v1'

S3_DATA_FILENAME = os.environ['S3_DATA_FILENAME']
S3_BUCKET_NAME = os.environ['S3_BUCKET_NAME']

TWILIO_ACCOUNT_SID = os.environ['TWILIO_ACCOUNT_SID']
TWILIO_AUTH_TOKEN = os.environ['TWILIO_AUTH_TOKEN']
TWILIO_TO_NUMBER = os.environ['TWILIO_TO_NUMBER']
TWILIO_FROM_NUMBER = os.environ['TWILIO_FROM_NUMBER']

#Amount of Drake songs I can listen to in a day
MAX_DRAKE_COUNT = 5

'''
TODO

Change to use EST timezone
'''

def sendTextMessage(count):
    client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
    message = "STOP LISTENING TO DRAKE, BRANDON. You've listened to him {count} times today".format(count=count)
    message = client.messages \
                .create(
                     body=message,
                     from_=TWILIO_FROM_NUMBER,
                     to=TWILIO_TO_NUMBER
                 )

def getAuthToken():
    token = util.prompt_for_user_token(username=SPOTIFY_USERNAME, 
                                   scope=SPOTIFY_SCOPE, 
                                   client_id=SPOTIFY_CLIENT_ID,   
                                   client_secret=SPOTIFY_CLIENT_SECRET,     
                                   redirect_uri=SPOTIFY_REDIRECT_URI)
    return token

def getTrackHistory(accessToken,after):
    headers = {
    'Authorization': 'Bearer {token}'.format(token=accessToken)
    }
    r = requests.get(SPOTIFY_BASE_URL + '/me/player/recently-played?limit=50&after=' + after, headers=headers)
    jsonData = r.json()
    print('json response: {response}'.format(response=jsonData))
    return jsonData


def lambda_handler(event, context):
    count = 0
    textSent = 'False'
    before = 1606876854372
    after = 1606876854378
    textSentTimestamp = 1606878643000
    todayCSVData = 1607169414000

    try:
        dataObject = s3.get_object(Bucket=S3_BUCKET_NAME, Key=S3_DATA_FILENAME)
        dataList = dataObject['Body'].read().decode('utf-8').rstrip().split(',')
        count = int(dataList[0])
        before = dataList[1]
        after = dataList[2]
        textSent = dataList[3]
        textSentTimestamp = int(dataList[4])
        todayCSVData = dataList[5]
    except Exception as e:
        print(e)
        raise e

    print('Debugging | Count: {count}, textSent: {textSent}, after: {after}, textSentTimestamp: {textSentTimestamp}'.format(count=count,textSent=textSent, after=after, textSentTimestamp=textSentTimestamp))

    accessToken = getAuthToken()
    recentTrackHistoryJsonData = getTrackHistory(accessToken=accessToken,after=after)


    afterDateTime = datetime.datetime.fromtimestamp(int(after)/1000.0).strftime('%Y-%m-%d')
    todayCSVDataStr = datetime.datetime.fromtimestamp(int(todayCSVData)/1000.0).strftime('%Y-%m-%d')
    today = date.today()
    nowComparedTime = datetime.datetime.now()

    if(today.strftime('%Y-%m-%d')>todayCSVDataStr):
        print('Its a new day, reset count to 0 and text sent to False\n')
        count = 0
        textSent = 'False'
        todayCSVData = int(time.time())*1000

    if(len(recentTrackHistoryJsonData['items']) > 0 ):
        for data in recentTrackHistoryJsonData['items']:
                for artists in data['track']['artists']:
                    if('Drake' in artists['name']):
                        count+=1
                    print(artists['name'])
    else:
        print('No tracks found\n')
    
    print( ('Drake count for today as of {today}: {COUNT}\n').format(today=nowComparedTime, COUNT=count))

    if(count>=MAX_DRAKE_COUNT and textSent in 'False'):
        textSent = 'True'
        textSentTimestamp = int(time.time())*1000
        print('SENDING TEXT MESSAGE\n')
        sendTextMessage(count=count)
    elif(count>=MAX_DRAKE_COUNT and textSent):
        futureSentTime = datetime.datetime.fromtimestamp(int(textSentTimestamp)/1000.0) + timedelta(minutes=90)
        if(nowComparedTime>futureSentTime):
            textSentTimestamp = int(time.time())*1000
            print('SENDING TEXT MESSAGE\n')
            sendTextMessage(count=count)
        else:
            print('DONT SEND MESSAGE will send on {nowComparedTime} | {futureSentTime}'.format(nowComparedTime=nowComparedTime, futureSentTime=futureSentTime))
    try:
        encodedString = ''
        if(len(recentTrackHistoryJsonData['items']) > 0 ):
            encodedString = '{count},{before},{after},{textSent},{textSentTimestamp},{todayCSVData}'.format(count=count, before=recentTrackHistoryJsonData['cursors']['before'], after=recentTrackHistoryJsonData['cursors']['after'], textSent=textSent, textSentTimestamp=textSentTimestamp,todayCSVData=todayCSVData)
            print('OUTPUT | {output}'.format(output=encodedString))
        else:
            encodedString = '{count},{before},{after},{textSent},{textSentTimestamp},{todayCSVData}'.format(count=count, before=before, after=after, textSent=textSent, textSentTimestamp=textSentTimestamp,todayCSVData=todayCSVData)
            print('OUTPUT (no tracks) | {output}'.format(output=encodedString))
        s3.put_object(Bucket=S3_BUCKET_NAME, Key=S3_DATA_FILENAME, Body=encodedString.encode("utf-8"))
    except Exception as e:
        print(e)
        raise e
