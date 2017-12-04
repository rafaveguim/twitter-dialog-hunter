
from bs4 import BeautifulSoup
import requests
import logging

class ConvoTweet:

    def __init__(self, user, tweet_id, convo_id, fullname, text):
        self.user = user
        self.id = tweet_id
        self.convo_id = convo_id
        self.fullname = fullname
        self.text = text


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
    def from_html(cls, html):
        soup = BeautifulSoup(html, "lxml")
        overlay = soup.find('div', id='permalink-overlay')
        tweets  = overlay.find_all('div', 'tweet')
        if tweets:
            for tweet in tweets:
                try:
                    yield cls.from_soup(tweet)
                except AttributeError:
                    pass  # Incomplete info? Discard!

    @classmethod
    def from_url(cls, url):
        html = requests.get(url).text
        for tweet in cls.from_html(html):
            yield tweet


# testing

# import requests
#
# url = 'https://twitter.com/ABakerN7/status/922558430640070658'
# # response = requests.get(url)
# tweets = list(ConvoTweet.from_url(url))
# tweets


# for t in tweets:
#     print(t.text)
#     print('-----')
