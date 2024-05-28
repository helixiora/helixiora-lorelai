# Getting started with LorelAI

In order to start working with LorelAI, please make sure you've followed all of the [prerequisites](./prerequisites.md). This guide only covers the app specific parts.

There are two ways LorelAI can be deployed/ran:

## Running in a python venv

1. Create a Python virtual environment: `python -m venv .venv`
1. Activate it with `source .venv/bin/activate`.
1. Install required dependencies: `pip install -r requirements.txt`. *N.B* this installs requirements for both the worker and web app. There's an additional requirements file for playing around with the more *experimental* features called requirements-dev.txt.
1. Get the database up and running, see the [readme in './db'](../db/readme.md)
1. Ensure all `.py` scripts are executable: `chmod +x indexer.py lorelaicli.py`.
1. Run an rq worker:

   `.venv/bin/rq worker &`

   ```log
    Worker rq:worker:dd2b92d43db1495383d426d5cb44ff79 started with PID 82721, version 1.16.1
    Subscribing to channel rq:pubsub:dd2b92d43db1495383d426d5cb44ff79
    *** Listening on default...
    Cleaning registries for queue: default

   ```

1. Launch the Flask application:

   ```bash
   export FLASK_APP=run.py
   flask run
   ```

   Note: add an `&` to `flask run` to have it run in the background, or use multiple terminals.

### Running using docker compose

1. Install and run [docker desktop](https://docs.docker.com/desktop/).
   1. On a mac, run `brew install docker` to install docker desktop
2. Get the stack  up and running using `docker-compose up --build`

### Initial setup of the app

1. Once you followed the steps and have an instance running, navigate to the local server URL ([http://127.0.0.1:5000](http://127.0.0.1:5000)).
    - You wil be asked to create an organisation if one doesn't exist in the MySQL database.
    - Note that this organization name will be the index name of the vector database folowing this structure: $env_name-$slug-$whatever_you_put_in_org_name
    - There's a limitation to the length of the index name sot the above string should not exceed 45 characters.
    - Follow the on-screen instructions to log in and authorize access to Google Drive.
1. Confirm that credentials are stored correctly in the database by querrying the `users` table, e.g:

    ```sql
     SELECT * FROM users;
    ```

### Chat application

Once logged in, you will see the chat interface at [http://127.0.0.1:5000](http://127.0.0.1:5000)

### Admin interface

Very rudimentary admin interface to see what you have stored in pinecone and run the indexer, accessible from [http://127.0.0.1:5000/admin](http://127.0.0.1:5000/admin)

### Executing the Indexer

#### From the command line

1. Initiate the document crawling process: `./indexer.py`. The indexer lives in [the tools directory](../tools/readme.md).
1. Check Pinecone to ensure your documents have been indexed successfully.

#### From the web UI

1. Go to [https://127.0.0.1:5000/admin](https://127.0.0.1:5000/admin) and press the indexer button
1. Check the rq worker logs in case something goes wrong

### Running Test Queries/CLI tool

You can test your queries using the `lorelaicli.py` tool. It is located in [the tools directory](../tools/readme.md)

## Remote live deployment

For deploying to any actual "production"-like environment we can see that obviously it won't work on the localhost URL. Also make sure to check the [prerequisites](prerequisites.md#non-local-deploy)
Otherwise the steps are the same for the time being.
