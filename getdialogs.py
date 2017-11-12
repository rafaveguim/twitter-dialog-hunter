# % cd collect_twitter_dialogs


import tweepy
import logging
import threading
import multiprocessing as mp
import argparse
import traceback
import twitter_dialogs
import tweetconvo

from time import time
from concurrent.futures import ThreadPoolExecutor
from requests_futures.sessions import FuturesSession
from configparser import ConfigParser
from en_top100 import top100 as top100_english


logging.basicConfig(level=logging.INFO)

class StreamListener(tweepy.StreamListener):
    """ Listens to on_status events from tweepy.Stream. Stores tweets on a buffer.
    Spawns N processes to consume the tweets. Each thread pops a tweet from the
    buffer and scans the author's timeline for conversations of a certain
    length. These conversations are stored and periodically written to a file.
    """

    def __init__(self, outfile_path, config_path, max_threads,
        max_processes, min_length, max_length):
        super().__init__()
        self.tweet_pool = []

        # stores batches of tweets to be shared with worker processes
        self.batch_pool = mp.Queue(20) # holds max 20 batches a time
        self.batch_size = 5

        self.outfile = open(outfile_path, 'a', encoding='utf-8')
        self.session = twitter_dialogs.get_session(config_path)

        self.min_length = min_length
        self.max_length = max_length

        self.max_threads = max_threads
        self.max_processes = max_processes
        self.processes = []

        self.flag_terminate = False # tells process to terminate

        for i in range(max_processes):
            process = mp.Process(target=self._consume,
                args=(self.batch_pool,),
                daemon=True)
            self.processes.append(process)
            process.start()

    def write_dialogs(self, dialogs):
        logging.info("Flushing {} dialogs..".format(len(dialogs)))

        for dialog in dialogs:
            for i, tweet in enumerate(dialog):
                fields = [
                    str(i),
                    tweet.id,
                    tweet.user,
                    self.clean_message(tweet.text)
                ]
                row = ','.join(fields)
                self.outfile.write(row +'\n')
            self.outfile.flush()

        logging.info("Flushing completed.")

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
        logger = logging.getLogger('Process ' + str(process_id))

        while not self.flag_terminate:
            if batch_pool.empty(): continue

            tweets = batch_pool.get()
            results = [] # all dialogs from the batch
            dialog_refs = dict() # stores the id of the first tweet in dialogs

            logger.info("Opened new batch containing {} tweets"\
                .format(len(tweets)))

            for tweet in tweets:
                # get timeline tweets using official API
                author = tweet.user.screen_name

                logger.info("Started scanning {}'s timeline.".format(author))

                timeline_tweets = twitter_dialogs.get_timeline_tweets(
                    self.session, author, 100, reply_only=True)

                if not timeline_tweets:
                    logger.warning("Unable to fetch {}'s timeline".format(author))
                    continue

                # each dialog has a url
                # (e.g., https://twitter.com/ABakerN7/status/922558430640070658)
                # use requests_futures to download pages async
                # and bs4 to scrap them

                session = FuturesSession(
                    executor=ThreadPoolExecutor(max_workers=self.max_threads))
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

                        # check if we already got this dialog
                        if dialog[0].id not in dialog_refs:
                            dialogs.append(dialog)
                            dialog_refs[dialog[0].id] = True

                    except Exception as e:
                        logging.error("Unable to parse {}".format(url))
                        print(e)

                n_valid = 0

                for dialog in dialogs:
                    if self.min_length <= len(dialog) <= self.max_length:
                        n_valid += 1
                        results.append(dialog)

                logger.info("Got {} dialogs from {}, {} are valid."\
                    .format(len(dialogs), author, n_valid, process_id))

            self.write_dialogs(results)

        logger.info("Process #{} terminated.".format(process_id))


    def clean_message(self, message):
        return message.replace('\n', '')

    def on_warning(self, notice):
        logging.info("A warning arrived: {}".format(notice))

    def on_event(self, status):
        logging.info("An event arrived: {}".format(status))

    def on_exception(self, exc):
        logging.error("An exception occurred. Trying to shutdown processes...")
        self.flag_terminate = True
        for process in self.processes:
            process.join(1)
        logging.error("All processes were terminated. Raising exception...")
        raise exc


    def on_status(self, tweet):
        if tweet.lang != 'en':
            return

        # get only the tweets that are part of a convo
        if tweet.in_reply_to_status_id is None:
            return

        self.enqueue_tweet(tweet)

    def on_error(self, status_code):
        logging.error("An error was caught (Status {})".format(status_code))
        # if status_code == 420:
        #     return False


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



def main(outfile_path, config_path, max_threads, max_processes,
    min_length, max_length):
    # listen to the stream for english tweets
    # then find author and look for conversations in their timelines

    while True:
        try:
            listener = StreamListener(outfile_path, config_path, max_threads,
                max_processes, min_length, max_length)
            myStream = tweepy.Stream(auth=get_auth(config_path),
                listener=listener)
            myStream.filter(track=top100_english, languages=['en'],
                stall_warnings=True)
        except Exception as e:
            myStream.disconnect()
            traceback.print_exc()
            logging.info("A new instance of the Stream will be created.")


def options():
    parser = argparse.ArgumentParser()
    parser.add_argument('outfile')
    parser.add_argument('--config', default='config.ini')
    parser.add_argument('-p', '--max_processes', type=int,
        help="the number of parallel workers (processes)")
    parser.add_argument('-t', '--max_threads', type=int, default=2,
        help="the max. # of threads a process can spawn for downloading pages")
    parser.add_argument('--min_length', type=int, default=2,
        help="the minimum length of a conversation")
    parser.add_argument('--max_length', type=int, default=999,
        help="the maximum length of a conversation")
    return parser.parse_args()


if __name__ == '__main__':
    opts = options()

    if not opts.max_processes:
        opts.max_processes = max([mp.cpu_count() - 1, 1])

    main(opts.outfile, opts.config, opts.max_threads, opts.max_processes,
        opts.min_length, opts.max_length)
