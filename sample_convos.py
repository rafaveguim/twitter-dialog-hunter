# % cd collect_twitter_dialogs


import tweepy
import logging
import threading
from time import time

from concurrent.futures import ThreadPoolExecutor
from requests_futures.sessions import FuturesSession
from configparser     import ConfigParser
from en_top100        import top100 as top100_english
import twitter_dialogs
import tweetconvo

logging.basicConfig(level=logging.INFO)

class StreamListener(tweepy.StreamListener):
    """ Listens to on_status events from tweepy.Stream. Stores tweets on a buffer.
    Spawns N threads to consume the tweets. Each thread pops a tweet from the
    buffer and scans the author's timeline for conversations of a certain
    length. These conversations are stored and periodically written to a file.
    """

    def __init__(self, outfile, max_threads=10):
        super().__init__()
        self.tweet_pool = []


        self.dialogs = []
        self.outfile = open(outfile, 'a', encoding='utf-8')
        self.session = twitter_dialogs.get_session('config.ini')
        self.flush_lock = threading.Lock()

        self.max_threads = max_threads
        self.thread_batch_size = 100

        self.threads = []


    def store_dialog(self, dialog):
        self.flush_lock.acquire()

        self.dialogs.append(dialog)

        if len(self.dialogs) >= 10:
            logging.info("Flushing {} dialogs..".format(len(self.dialogs)))
            # flush
            while len(self.dialogs) > 0:
                dialog = self.dialogs.pop()
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

        self.flush_lock.release()

    def enqueue_tweet(self, tweet):
        # hold max 1000 tweets at a time
        if len(self.tweet_pool) < 1000:
            self.tweet_pool.append(tweet)

        # if we have enough tweets and we haven't reached the max # of threads
        # then spawn a new thread
        if len(self.tweet_pool) >= self.thread_batch_size and \
            self.max_threads > len(self.threads):

            batch = []
            for _ in range(self.thread_batch_size):
                batch.append(self.tweet_pool.pop())

            thread = threading.Thread(target=self._consume, args=(batch,))
            thread.start()

    def _consume(self, tweets):
        """
        Consumes tweets from self.tweet_pool. For each tweet,
        tries to find conversations in the author's timeline.
        """
        for tweet in tweets:

            # get timeline tweets using official API
            author = tweet.user.screen_name
            timeline_tweets = twitter_dialogs.get_timeline_tweets(
                self.session, author, 100, reply_only=True)

            # each conversation has a url
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
                    self.store_dialog(dialog)

            logging.info("Got {} dialogs for {}, {} are valid. Thread #{}"\
                .format(len(dialogs), author, n_valid, threading.get_ident()))

        # remove itself from self.threads
        self.threads.remove(threading.current_thread())

    def clean_message(self, message):
        return message.replace('\n', '')

    def on_status(self, tweet):
        if tweet.lang != 'en':
            return

        # get only the tweets that are part of a convo
        if tweet.in_reply_to_status_id is None:
            return

        self.enqueue_tweet(tweet)

    # def on_error(self, status_code):
    #     if status_code == 420:
    #         #returning False in on_data disconnects the stream
    #         return False
    #     else:
    #
    #         pass

def get_auth(config_file):
    config = ConfigParser()
    config.read(config_file)

    consumer_key    = config.get('AccessKeys', 'ConsumerKey')
    consumer_secret = config.get('AccessKeys', 'ConsumerSecret')
    access_token    = config.get('AccessKeys', 'AccessToken')
    access_secret   = config.get('AccessKeys', 'AccessTokenSecret')

    auth = tweepy.OAuthHandler(consumer_key, consumer_secret)
    auth.set_access_token(access_token, access_secret)

    return auth


OUTFILE = '/Users/rafa/Data/twitter-convos/convos-6.csv'
BLOOM_FILTER = '/Users/rafa/Data/twitter-convos/bloom.pickle'

# listen to the stream for english tweets
# then find author and look for conversations in their timelines
myStream = tweepy.Stream(auth=get_auth('config.ini'),
    listener=StreamListener(OUTFILE))
myStream.filter(track=top100_english, languages=['en'], stall_warnings=True)

# TODO:
# 1) Work around truncated statuses. Possibly, follow link
# with fake_useragent and extract tweet with beautifulsoup
# 2) Store bloomfilter to make sure we don't get repeated tweets
# 3) Make beautifulsoup-based functions to extract tweets
#
