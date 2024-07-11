# Getting started with LorelAI

In order to start working with LorelAI, please make sure you've followed all of the
[prerequisites](./prerequisites.md). This guide only covers the app specific parts.

There are two ways LorelAI can be deployed/ran:

## Running in a python venv

1. Create a Python virtual environment: `python -m venv .venv`

1. Activate it with `source .venv/bin/activate`.

1. Install required dependencies: `pip install -r requirements.txt`. _N.B_ this installs
   requirements for both the worker and web app. There's an additional requirements file for playing
   around with the more _experimental_ features called requirements-dev.txt.

1. Get the database up and running, see the [readme in './db'](../db/readme.md)

1. Create a `settings.json` file (see `settings.json.example`) and customise the values to your
   liking

   1. You'll need a google cloud project for oauth

   1. You'll need a pinecone API key

   1. You need to setup Olama with Llama3 or use an OpenAI API key

   See [prerequisites](./prerequisites.md) for more info

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
1. Get the stack up and running using `docker-compose up --build`

### Initial setup of the app

1. Once you followed the steps and have an instance running, navigate to the local server URL
   ([https://127.0.0.1:5000](https://127.0.0.1:5000)).

   - You will be asked to create an organisation if one doesn't exist in the MySQL database.
   - Note that this organization name will be the index name of the vector database following this
     structure: $env_name-$slug-$whatever_you_put_in_org_name
   - There's a limitation to the length of the index name sot the above string should not exceed 45
     characters.
   - Follow the on-screen instructions to log in and authorize access to Google Drive.

1. Confirm that credentials are stored correctly in the database by querying the `users` table, e.g:

   ```sql
    SELECT * FROM users;
   ```

### Chat application

Once logged in, you will see the chat interface at [https://127.0.0.1:5000](https://127.0.0.1:5000)

### Admin interface

Very rudimentary admin interface to see what you have stored in pinecone and run the indexer,
accessible from [https://127.0.0.1:5000/admin](https://127.0.0.1:5000/admin)

### Executing the Indexer

#### From the command line

1. Initiate the document crawling process: `./indexer.py`. The indexer lives in
   [the tools directory](../tools/readme.md).
1. Check Pinecone to ensure your documents have been indexed successfully.

#### From the web UI

1. Go to [https://127.0.0.1:5000/admin](https://127.0.0.1:5000/admin) and press the indexer button
1. Check the rq worker logs in case something goes wrong

### Running Test Queries/CLI tool

You can test your queries using the `lorelaicli.py` tool. It is located in
[the tools directory](../tools/readme.md)

## Remote live deployment

For deploying to any actual "production"-like environment we can see that obviously it won't work on
the localhost URL. Also make sure to check the [prerequisites](prerequisites.md#non-local-deploy)
Otherwise the steps are the same for the time being.

## debugging with VS code

Use the below settings to create configurations so you can debug from VS code:

```json
{
  // Use IntelliSense to learn about possible attributes.
  // Hover to view descriptions of existing attributes.
  // For more information, visit: https://go.microsoft.com/fwlink/?linkid=830387
  "version": "0.2.0",
  "configurations": [
    {
      // Configuration to run the RQ worker
      "name": "RQ Worker",
      "type": "debugpy",
      "request": "launch",
      "module": "rq.cli",
      "env": {
        // Specify the Redis URL
        "RQ_REDIS_URL": "redis://localhost:6379/0",
        // log level
        "LOG_LEVEL": "DEBUG"
      },
      "args": [
        "worker" // Run the RQ worker
      ],
      // Specify where the program output goes
      "console": "internalConsole"
    },
    {
      // Configuration name
      "name": "Flask",

      // Type of configuration - use debugpy for Python
      "type": "debugpy",

      // Request type - launch the Flask module
      "request": "launch",

      // The Python module to launch
      "module": "flask",

      // Environment variables
      "env": {
        // Specify the entry point of the Flask application
        "FLASK_APP": "run.py",
        // Enable Flask debug mode
        "FLASK_DEBUG": "1",
        "LOG_LEVEL": "DEBUG"
      },

      // Arguments passed to the Flask application
      "args": [
        "run", // Run the Flask application
        "--no-debugger", // Disable the Flask debugger
        "--no-reload", // Disable the reloader
        "--cert",
        "./cert.pem", // Path to the SSL certificate
        "--key",
        "key.pem" // Path to the SSL key
      ],

      // Enable Jinja templating
      "jinja": true,

      // Common Parameters
      // Specify the working directory for the Flask application
      "cwd": "${workspaceFolder}",

      // Debug only user-written code, ignoring library files
      "justMyCode": true,

      // Specify where the program output goes
      "console": "internalConsole",

      // Redirect logs to a specific file (optional)
      "logToFile": true
    }
  ],
  "compounds": [
    {
      "name": "Compound",
      "configurations": ["Flask", "RQ Worker"]
    }
  ]
}
```
