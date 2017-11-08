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

    ```
    $ pip install -r requirements.txt
    ```

## How to use:

  ```
  python getdialogs.py --help
  ```

  If you need dialogs with 4 to 6 turns, for example:

  ```
  python getdialogs.py \
        --min_length=4 \
        --max_length=6 \
        output.csv
  ```

  The script will collect data until interrupted (`Ctrl+c`). It will
  periodically save the collected dialogs to the informed path, which is
  `output.csv` above. Dialogs are _appended_ to the output file, so it's
  OK to stop and restart the script later. Previous results will not be lost.

  You can inform the path to a custom config file with `--config`. This is useful
  for when you have many set of credentials. Each run can use a different set to
  avoid rate-limiting.


## Resource Balancing

  By default, the script tries to maximize the use of resources by splitting the
  workload among processes. The number of such
  processes can be set with `--max_processes`. By default, this is set
  to the number of cores available in the machine. This may be the best setting
  if running in a dedicated node. If you're running the script casually in
  a laptop, a less aggressive value for this setting should be more appropriate.

  Similarly you can set the maximum number of threads to be used by each
  process in `--max_threads`. This value should be carefully chosen. If too
  high (e.g. 10), the threads will compete with the thread that listens to
  the Streaming API, causing it to fall behind. When a client fails to keep up with
  the stream, Twitter disconnects it.
