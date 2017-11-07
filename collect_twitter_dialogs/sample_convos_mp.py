# % cd collect_twitter_dialogs


import tweepy
import logging
import threading
import multiprocessing as mp
import argparse

from time import time
from concurrent.futures import ThreadPoolExecutor
from requests_futures.sessions import FuturesSession
from configparser import ConfigParser
from en_top100 import top100 as top100_english
import twitter_dialogs
import tweetconvo

logging.basicConfig(level=logging.INFO)

class StreamListener(tweepy.StreamListener):
    """ Listens to on_status events from tweepy.Stream. Stores tweets on a buffer.
    Spawns N processes to consume the tweets. Each thread pops a tweet from the
    buffer and scans the author's timeline for conversations of a certain
    length. These conversations are stored and periodically written to a file.
    """

    def __init__(self, outfile_path, config_path, max_processes=4):
        super().__init__()
        self.tweet_pool = []

        # stores batches of tweets to be shared with worker processes
        self.batch_pool = mp.Queue(20) # holds max 20 batches a time
        self.batch_size = 5

        self.outfile = open(outfile_path, 'a', encoding='utf-8')
        self.session = twitter_dialogs.get_session(config_path)

        self.max_processes = max_processes

        for i in range(max_processes):
            process = mp.Process(target=self._consume,
                args=(self.batch_pool,),
                daemon=True)
            process.start()

    def write_dialogs(self, dialogs):
        logging.info("Flushing {} dialogs..".format(len(dialogs)))

        for dialog in dialogs:
            for i, tweet in enumerate(dialog):
                fields = [
                    str(i),
                    tweet.id,
                    tweet.user,
                    self.clean_message(tweet.text),
                ]
                row = ','.join(fields)
                self.outfile.write(row +'\n')
            self.outfile.flush()

        logging.info("Flushing completed.")
        logging.info("Tweet pool has {} tweets."
            .format(len(self.tweet_pool)))

    def enqueue_tweet(self, tweet):
        # hold max 10*batch_size tweets at a time
        if len(self.tweet_pool) < 10*self.batch_size:
            self.tweet_pool.append(tweet)

        # if there's room in the batch_pool and we have enough tweets for a new
        # batch, then enqueue a new batch
        if not self.batch_pool.full() and \
            len(self.tweet_pool) >= self.batch_size:

            batch = []
            for _ in range(self.batch_size):
                batch.append(self.tweet_pool.pop())
            self.batch_pool.put(batch)

    def _consume(self, batch_pool):
        """
        Consumes tweets from self.batch_pool. For each tweet in a pool,
        tries to find conversations in the author's timeline.
        Then writes them to a file.
        """
        process_id = mp.current_process()._identity[0]
        logger = logging.getLogger('Process' + str(process_id))

        while True:
            if batch_pool.empty(): continue

            tweets = batch_pool.get()
            results = [] # all dialogs from the batch

            logger.info("Opened new batch containing {} tweets"\
                .format(len(tweets)))

            for tweet in tweets:


                # get timeline tweets using official API
                author = tweet.user.screen_name
                timeline_tweets = twitter_dialogs.get_timeline_tweets(
                    self.session, author, 100, reply_only=True)

                # each dialog has a url
                # (e.g., https://twitter.com/ABakerN7/status/922558430640070658)
                # use requests_futures to download pages async
                # and bs4 to scrap them

                session = FuturesSession(executor=ThreadPoolExecutor(max_workers=10))
                futures = []
                for i, timeline_tweet in enumerate(timeline_tweets):
                    url = 'https://twitter.com/i/web/status/{}'\
                        .format(timeline_tweet.id)
                    futures.append((url, session.get(url)))

                # parse each dialog with bs4
                dialogs = []
                for url, future in futures:
                    try:
                        html = future.result().text
                        dialog = list(tweetconvo.ConvoTweet.from_html(html))
                        dialogs.append(dialog)
                    except Exception as e:
                        logging.error("Unable to parse {}".format(url))
                        print(e)

                n_valid = 0

                for dialog in dialogs:
                    if len(dialog) == 6:
                        n_valid += 1
                        results.append(dialog)

                logger.info("Got {} dialogs for {}, {} are valid. Process #{}"\
                    .format(len(dialogs), author, n_valid, process_id))

            self.write_dialogs(results)

    def clean_message(self, message):
        return message.replace('\n', '')

    def on_status(self, tweet):
        if tweet.lang != 'en':
            return

        # get only the tweets that are part of a convo
        if tweet.in_reply_to_status_id is None:
            return

        self.enqueue_tweet(tweet)


def get_auth(config_path):
    config = ConfigParser()
    config.read(config_path)

    consumer_key    = config.get('AccessKeys', 'ConsumerKey')
    consumer_secret = config.get('AccessKeys', 'ConsumerSecret')
    access_token    = config.get('AccessKeys', 'AccessToken')
    access_secret   = config.get('AccessKeys', 'AccessTokenSecret')

    auth = tweepy.OAuthHandler(consumer_key, consumer_secret)
    auth.set_access_token(access_token, access_secret)

    return auth


# OUTFILE = '/Users/rafa/Data/twitter-convos/convos-6.csv'
BLOOM_FILTER = '/Users/rafa/Data/twitter-convos/bloom.pickle'


def main(outfile_path, config_path, max_processes):
    # listen to the stream for english tweets
    # then find author and look for conversations in their timelines
    myStream = tweepy.Stream(auth=get_auth(config_path),
        listener=StreamListener(outfile_path, config_path, max_processes))

    while True:
        try:
            myStream.filter(track=top100_english, languages=['en'],
                stall_warnings=True)
        except Exception as e:
            print(e)


def options():
    parser = argparse.ArgumentParser()
    parser.add_argument('config')
    parser.add_argument('outfile')
    parser.add_argument('-p', '--max_processes', type=int)
    return parser.parse_args()


if __name__ == '__main__':
    opts = options()
    if not opts.max_processes:
        opts.max_processes = max([mp.cpu_count() - 1, 1])

    main(opts.outfile, opts.config, opts.max_processes)


# TODO:
# + (Done) Work around truncated statuses. Possibly, follow link
# with fake_useragent and extract tweet with beautifulsoup
# + (Done) Make beautifulsoup-based functions to extract tweets
# + Store bloomfilter to make sure we don't get repeated tweets
# + Make as much as the process as possible based on BS4 (to avoid getting rate
#   limit)
#
#
