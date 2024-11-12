# Getting started with LorelAI

In order to start working with LorelAI, please make sure you've followed all of the
[prerequisites](./prerequisites.md). This guide only covers the app specific parts.

There are two ways LorelAI can be deployed/ran:

## Running in a python venv

1. Create a Python virtual environment: `python -m venv .venv`

1. Activate it with `source .venv/bin/activate`.

1. Install required dependencies: `pip install -r requirements.txt`. repeat for
   `requirements-dev.txt`, `requirements-web.txt` and `requirements-worker.txt`

1. Get the database up and running, see the [readme in './migrations'](../migrations/readme.md)

1. Create a `.env` file (see `.env.example`) and customise the values to your liking

   1. You'll need a google cloud project for oauth

   1. You'll need a pinecone API key

   1. You need to setup Olama with Llama3 or use an OpenAI API key

   See [prerequisites](./prerequisites.md) for more info

1. Run an rq worker with all three queues:

   `.venv/bin/rq worker indexer_queue question_queue default &`

   ```log
    Worker rq:worker:dd2b92d43db1495383d426d5cb44ff79 started with PID 82721, version 1.16.1
    Subscribing to channel rq:pubsub:dd2b92d43db1495383d426d5cb44ff79
    *** Listening on default...
    Cleaning registries for queue: default

   ```

1. Launch the Flask application:

   ```bash
   export FLASK_APP=run.py
   flask run --debug --cert ./cert.pem --key key.pem
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
   - Note that this organisation name will be the index name of the vector database following this
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

#### From the web UI

1. Go to [https://127.0.0.1:5000/admin](https://127.0.0.1:5000/admin) and press the indexer button
1. Check the rq worker logs in case something goes wrong

### Running Test Queries/CLI tool

(NOTE: this is not currently used) You can test your queries using the `lorelaicli.py` tool. It is
located in [the tools directory](../tools/readme.md)

## Remote live deployment

For deploying to any actual "production"-like environment we can see that obviously it won't work on
the localhost URL. Also make sure to check the [prerequisites](prerequisites.md#non-local-deploy)
Otherwise the steps are the same for the time being.

## debugging with VS code

Use the below settings to create configurations so you can debug from VS code:

In `.vscode/launch.json`:

```json
{
  "version": "0.2.0",
  "configurations": [
      {
          "name": "RQ Worker with Debugpy",
          "type": "debugpy",
          "request": "launch",
          "module": "rq.cli",
          "args": [
              "worker",
              "-c", "4",
              "indexer_queue",
              "question_queue",
              "default"
          ],
          "env": {
              "RQ_REDIS_URL": "redis://localhost:6379/0",
              "OBJC_DISABLE_INITIALIZE_FORK_SAFETY": "1",
              "LOG_LEVEL": "INFO",
              "NO_PROXY": "*"
          },
          "console": "integratedTerminal",
          "consoleName": "RQ Worker",
          "justMyCode": false,
          "subProcess": true
      },
      {
          "name": "Flask Debug",
          "type": "debugpy",
          "request": "launch",
          "module": "flask",
          "env": {
              "FLASK_APP": "run.py",
              "FLASK_ENV": "development",
              "FLASK_DEBUG": "1",
              "OBJC_DISABLE_INITIALIZE_FORK_SAFETY": "1",
              "LOG_LEVEL": "INFO"
          },
          "args": [
              "run",
              "--cert=./cert.pem",
              "--key=./key.pem",
              "--host=0.0.0.0",
              "--port=5000",
              "--debug"
          ],
          "console": "integratedTerminal",
          "consoleName": "Flask app",
          "jinja": true,
          "justMyCode": false,
          "subProcess": true
      }
  ],
  "compounds": [
      {
          "name": "Flask and RQ Worker with Debugpy",
          "configurations": [
              "Flask Debug",
              "RQ Worker with Debugpy"
          ]
      }
  ]
}

```

In `.vscode/tasks.json`:

```json
{
    "version": "2.0.0",
    "tasks": [
        {
            "label": "Start RQ Dashboard",
            "type": "shell",
            "command": "${command:python.interpreterPath}",
            "args": [
                "-m",
                "rq_dashboard",
                "--port",
                "9181",
                "--redis-url",
                "redis://localhost:6379/0"
            ],
            "isBackground": true,
            "problemMatcher": {
                "pattern": {
                    "regexp": "^$",
                    "file": 1,
                    "location": 2,
                    "message": 3
                },
                "background": {
                    "activeOnStart": true,
                    "beginsPattern": "^.*Running on.*$",
                    "endsPattern": "^.*Running on.*$"
                }
            }
        },
        {
            "label": "Open RQ Dashboard in Browser",
            "type": "shell",
            "command": "open",
            "args": ["http://localhost:9181"],
            "presentation": {
                "reveal": "never",
                "close": true
            },
            "dependsOn": "Start RQ Dashboard"
        },
        {
            "label": "Start Lorelai in Browser",
            "type": "shell",
            "command": "open",
            "args": ["https://127.0.0.1:5000"],
            "presentation": {
                "reveal": "never",
                "close": true
            }
        }
    ]
}
```
