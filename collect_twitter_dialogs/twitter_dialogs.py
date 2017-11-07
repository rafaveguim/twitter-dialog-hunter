#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""collect_twitter_dialogs.py:
   A script to acquire twitter dialogs with REST API 1.1.

   Copyright (c) 2017 Takaaki Hori  (thori@merl.com)

   This software is released under the MIT License.
   http://opensource.org/licenses/mit-license.php

"""

import argparse
import json
import sys
import six
import os
import re
import time
import logging
from requests_oauthlib import OAuth1Session
from twitter_api import GETStatusesUserTimeline
from twitter_api import GETStatusesLookup
import tweepy

try:
    from configparser import ConfigParser
except ImportError:
    from ConfigParser import SafeConfigParser as ConfigParser

# create logger object
logger = logging.getLogger("root")
logger.setLevel(logging.INFO)


def get_session(config_path):
    # get access keys from a config file
    config = ConfigParser()
    config.read(config_path)
    ConsumerKey = config.get('AccessKeys','ConsumerKey')
    ConsumerSecret = config.get('AccessKeys','ConsumerSecret')
    AccessToken = config.get('AccessKeys','AccessToken')
    AccessTokenSecret = config.get('AccessKeys','AccessTokenSecret')

    return OAuth1Session(
        ConsumerKey,
        ConsumerSecret,
        AccessToken,
        AccessTokenSecret)

def get_dialogs(session, username, count):
    # setup API object
    get_user_timeline = GETStatusesUserTimeline(session)
    get_user_timeline.setParams(target_count=count, reply_only=True)
    get_lookup = GETStatusesLookup(session)

    # collect dialogs from each target
    num_dialogs = 0
    num_past_dialogs = 0

    since_id = None
    dialog_set = {}

    get_user_timeline.setParams(username, max_id=None, since_id=since_id)
    get_user_timeline.waitReady()
    timeline_tweets = get_user_timeline.call()

    if not timeline_tweets:
        return []

    ## collect source tweets
    tweet_set = {}

    ## add new tweets and collect reply-ids as necessary
    source_ids = set()
    for tweet in timeline_tweets:
        tweet_set[tweet['id']] = tweet
        reply_id = tweet['in_reply_to_status_id']
        if reply_id is not None and reply_id not in tweet_set:
            source_ids.add(reply_id)

    ## acquire source tweets
    get_lookup.waitReady()
    while len(source_ids) > 0:
        get_lookup.setParams(source_ids)
        result = get_lookup.call()
        new_source_ids = set()
        for tweet in result:
            tweet_set[tweet['id']] = tweet
            reply_id = tweet['in_reply_to_status_id']
            if reply_id is not None and reply_id not in tweet_set:
                new_source_ids.add(reply_id)
        source_ids = new_source_ids

    ## reconstruct dialogs
    visited = set()
    new_dialogs = 0
    for tweet in timeline_tweets:
        tid = tweet['id']
        if tid not in visited: # ignore visited node (it's not a terminal)
            visited.add(tid)
            # backtrack source tweets and make a dialog
            dialog = [tweet]
            reply_id = tweet_set[tid]['in_reply_to_status_id']
            while reply_id is not None:
                visited.add(reply_id)

                if reply_id in tweet_set:
                    dialog.insert(0,tweet_set[reply_id])
                else:
                    break
                # move to the previous tweet
                reply_id = tweet_set[reply_id]['in_reply_to_status_id']

            # add the dialog only if it contains two or more turns,
            # where it is associated with its terminal tweet id.
            if len(dialog) > 1:
                dialog_set[str(tid)] = dialog
                new_dialogs += 1

    return list(dialog_set.values())


def get_timeline_tweets(session, username, count=0, reply_only=True):
    # setup API object
    get_user_timeline = GETStatusesUserTimeline(session)
    get_user_timeline.setParams(target_count=count, reply_only=reply_only)
    get_lookup = GETStatusesLookup(session)

    # collect dialogs from each target
    num_dialogs = 0
    num_past_dialogs = 0

    since_id = None
    dialog_set = {}

    get_user_timeline.setParams(username, max_id=None, since_id=since_id)
    get_user_timeline.waitReady()

    tweets_json = get_user_timeline.call()
    statuses = []
    # wrap our JSON tweets into nice Tweepy Status objects
    for tweet in tweets_json:
        statuses.append(tweepy.models.Status.parse(tweepy.API(), tweet))

    return statuses


# testing

# session = get_session('config.ini')
#
# dialogs = get_dialogs(session, 'sharoz', 1)
#
# rows = []
# for dialog in dialogs:
#     if len(dialog) !=  6:
#         continue
#     for tweet in dialog:
#         fields = [
#             tweet['id'],
#             tweet['user']['screen_name'],
#             tweet['text'],
#         ]
#         rows.append(','.join(fields))
#
# dialogs[0]
#
# ---------------------------------------------------
# #
#
# import tweetconvo
# import requests
# session = get_session('config.ini')
# tweets = get_timeline_tweets(session, 'ABakerN7', 50)
#
# for t in tweets:
#     reply_id = t.in_reply_to_status_id
#     if reply_id:
#         url = 'https://twitter.com/i/web/status/{}'.format(t.id)
#         convo = tweetconvo.ConvoTweet.from_html(requests.get(url).text)
#         for c in convo:
#             print(c.text)
#         break

# session = get_session('config.ini')
# tweets = get_timeline_tweets(session, 'rafaveguim', 100)
# for tweet in tweets:
#     # if tweet.in_reply_to_status_id is None:
#     print(tweet.in_reply_to_status_id)
#
# import tweetconvo
# # %cd collect_twitter_dialogs
# url = 'https://twitter.com/i/web/status/{}'\
#     .format(tweets[0].id)
# dialog = list(tweetconvo.ConvoTweet.from_url(url))
# dialog
