# Twitter Dialog Hunter

This Python script uses the Twitter API and BeautifulSoup to
find and download dialogs from Twitter. It is built on top of the
`collect_twitter_dialogs` module from DSTC6-End-to-End-Conversation-Modeling.

It is meant to overcome some limitations of the DSTC6 module and other
scrapers. The script doesn't require a list of source accounts,
and for the most part avoids rate-limiting by scraping public urls. You can
define the desired range of dialog length, and scale the execution across cores
and treads.


## Preparation

1. create a twitter account if you don't have it.

    you can get it via <https://twitter.com/signup>

2. create your application account via the Twitter

    Developer's Site: <https://dev.twitter.com/>

    see <https://iag.me/socialmedia/how-to-create-a-twitter-app-in-8-easy-steps/>  

    for reference, and keep the following keys

   * Consumer Key
   * Consumer Secret
   * Access Token
   * Access Token Secret  

3. edit ./config.ini to set your access keys in the config file

   * ConsumerKey
   * ConsumerSecret
   * AccessToken
   * AccessTokenSecret  

4. install dependencies

    you can install them in the system area by

    ```
    $ pip install -r requirements.txt
    ```

## How to use:

  If you need dialogs with 4 to 6 turns, for example:

  ```
  python getdialogs.py \
        --min_length=4 \
        --max_length=6 \
        config.ini \
        dialogs-4-6.csv
  ```
