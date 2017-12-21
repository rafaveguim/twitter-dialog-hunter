
from bs4 import BeautifulSoup
import requests
import logging


class Tweet:
    """
    A tweet that belongs to a conversation.
    """

    def __init__(self, user, tweet_id, fullname, text, convo_id=None):
        self.user = user
        self.id = tweet_id
        self.convo_id = convo_id
        self.fullname = fullname
        self.text = text

    def is_reply(self):
        return self.convo_id != self.id

    @classmethod
    def from_soup(cls, tweet):
        return cls(
            user=tweet['data-screen-name'],
            tweet_id=tweet['data-tweet-id'],
            convo_id=tweet['data-conversation-id'],
            fullname=tweet['data-name'],
            text=tweet.find('p', 'js-tweet-text').text or ""
        )

    @classmethod
    def from_conversation(cls, html):
        soup = BeautifulSoup(html, "lxml")
        overlay = soup.find('div', id='permalink-overlay')
        tweets  = overlay.find_all('div', 'tweet')
        if tweets:
            for tweet in tweets:
                try:
                    yield cls.from_soup(tweet)
                except AttributeError:
                    pass  # Incomplete info? Discard!
                except KeyError:
                    pass

    # @classmethod
    # def from_timeline(cls, username, max_count=200, reply_only=False):
    #     session = requests.Session()
    #     url = "https://twitter.com/{}/with_replies".format(username)
    #     response = session.get(url)
    #     html = response.text
    #     soup = BeautifulSoup(html, "lxml")
    #
    #     # username = (soup.find('a', class_='ProfileHeaderCard-screennameLink')
    #     #                 .find('span', class_="username")
    #     #                 .find('b').text)
    #     tweets = soup.find_all('div', attrs={'class': 'tweet',
    #                                          'data-screen-name': username})
    #     print(len(tweets))
    #
    #     #  To retrieve Tweets further back in time, we need to set the max_position
    #     #  parameter in the next call. it should be the id of the oldest (last)
    #     #  tweet retrieved in the present call.
    #     # min_position = soup.find('div', attrs={'data-min-position': True}) \
    #     #                    .attrs['data-min-position']
    #     max_position = tweets[-1].attrs['data-tweet-id']
    #
    #     has_more_items = True
    #     while has_more_items and len(tweets) < max_count:
    #         moretweets_url = ("https://twitter.com/i/profiles/show/{}"
    #             "/timeline/tweets?include_available_features=1&"
    #             "include_entities=1&max_position={}&reset_error_state=false") \
    #             .format(username, max_position)
    #
    #         response = session.get(moretweets_url)
    #         rjson = response.json()
    #         soup = BeautifulSoup(rjson['items_html'], 'lxml')
    #         newtweets = soup.find_all('div',
    #             attrs={'class': 'tweet', 'data-screen-name': username})
    #
    #         tweets.extend(newtweets)
    #
    #         has_more_items = rjson['has_more_items']
    #         max_position   = rjson['min_position']
    #
    #     if tweets:
    #         for tweet in tweets:
    #             try:
    #                 tweet_obj = cls.from_soup(tweet)
    #                 if not reply_only or tweet_obj.is_reply():
    #                     yield tweet_obj
    #             except AttributeError:
    #                 pass  # Incomplete info? Discard!

    @classmethod
    def from_timeline(cls, username, max_count=200, reply_only=False):
        # this page explains where to find the Bearer token:
        # https://github.com/rg3/youtube-dl/issues/12726
        # also, we can just look the browser request headers
        bearer_token = ("AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs%3D"
                       "1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA")
        headers = {'authorization': 'BEARER {}'.format(bearer_token)}

        params = {
            'include_profile_interstitial_type':1,
            'skip_status':1,
            'include_tweet_replies': True,
            'include_rts': False,
            'screen_name': username,
            'count':max_count
            }
        url = 'https://api.twitter.com/1.1/statuses/user_timeline.json'
        response = requests.get(url, params=params, headers=headers)
        rjson = response.json()

        if response.status_code != 200:
            logging.error("{} returned status {}".format(url, response.status_code))
            return []
        if type(rjson) != dict:
            logging.error("{} returned the following message: {}".format(url, rjson))
            return []

        for tweet_json in rjson:
            if reply_only and tweet_json['in_reply_to_user_id'] is None:
                continue

            yield cls(
                        user=tweet_json['user']['screen_name'],
                        tweet_id=tweet_json['conversation_id'],
                        convo_id=tweet_json['id'],
                        fullname=tweet_json['user']['name'],
                        text=tweet_json['text']
                    )

    @classmethod
    def from_url(cls, url):
        html = requests.get(url).text
        for tweet in cls.from_html(html):
            yield tweet



# =============================
# response = requests.get('https://twitter.com/i/web/status/943135577532137473')
# response.text
# tweets = list(Tweet.from_conversation(response.text))
# tweets

# tweets = list(Tweet.from_timeline('rafaveguim', reply_only=True))
# len(tweets)
# for t in tweets:
#     print(t.text)


#
# url = 'https://twitter.com/ABakerN7/status/922558430640070658'
# # response = requests.get(url)
# tweets = list(ConvoTweet.from_url(url))
# tweets


# for t in tweets:
#     print(t.text)
#     print('-----')
