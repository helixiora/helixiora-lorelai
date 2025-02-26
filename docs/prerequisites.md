# Prerequisites

## MySQL

### Installation

In order to store user and organisation data we utilize MySQL, though we recommend going with
MariaDB. Please make sure to install it using
[the documentation](https://mariadb.com/kb/en/getting-installing-and-upgrading-mariadb/) for your
operating system and that it's reachable from the Lorelai instance.

### Setup

Once installed, make sure to create a user with the approapriate grants:

1. Connect to your MySQL instance (default installs allow access from root without password
   `$ sudo mysql`).
1. For development, create a user
   `grant all on *.* to '$USER'@'$HOST_WHERE_LORELAI_LIVES' identified by '$PASSWORD';`. Here the
   $HOST_WHERE_LORELAI_LIVES is where you would launch the app, particularly the IP which the MySQL
   instance will see as the inbound connection. For local installs simply use 'localhost' or
   '127.0.0.1' here.
1. Once this is set up and these credentials are in `settings.json` you can start the web ui. It
   will automatically redirect you to a page where you can create the database schema.

## Redis

Please make sure to follow official documentation for installing Redis on your distribution of
choice. Below is a general guide. Also note that when deploying with the supplied docker stack files
they also deploy a redis instance.

### On Linux

1. Ubuntu/Debian:

   ```bash
   sudo apt update
   sudo apt install redis-server
   ```

1. CentOS/RedHat

   ```bash
   sudo yum install epel-release
   sudo yum install redis
   sudo systemctl start redis
   sudo systemctl enable redis
   ```

1. On macOS:

   ```bash
   brew install redis
   ```

## Obtain API Keys and Credentials

1. Obtain a Pinecone API key from [Pinecone's portal](https://app.pinecone.io/organisations/). Make
   sure this is a key owned by Helixiora so we pick up the bill, not you.
1. Acquire an OpenAI API key through [OpenAI's platform](https://platform.openai.com/api-keys). Make
   sure this is a key owned by Helixiora so we pick up the bill, not you.
1. Generate Google OAuth credentials via
   [Google Cloud Console](https://console.cloud.google.com/apis/credentials). Make sure this is in
   the project owned by Helixiora so we pick up the bill, not you.

## Configuration variables

In order to pass these keys, connection strings for the MySQL database etc you have two options:

### .env settings file

The [example settings](../.env.example) file contains examples of all

## Env vars

You can export the following env vars either through Docker or your local shell.

```bash
GOOGLE_CLIENT_ID
GOOGLE_PROJECT_ID
GOOGLE_AUTH_URI
GOOGLE_TOKEN_URI
GOOGLE_AUTH_PROVIDER_X509_CERT_U
GOOGLE_CLIENT_SECRET
GOOGLE_REDIRECT_URIS
PINECONE_API_KEY
OPENAI_API_KEY
LORELAI_ENVIRONMENT
LORELAI_ENVIRONMENT_SLUG
LORELAI_REDIRECT_URI
DB_HOST
DB_USER
DB_DATABASE
DB_PASSWORD
```

Note that the project id is the id of the project in the
[google console](https://console.cloud.google.com/cloud-resource-manager). All of the GOOGLE\_
prepended ones are available there actually.

## non-local-deploy

When deploying to remote-accessible environments you need to make a couple of considerations:

1. The Redirect URI used for Google Oauth needs to be https. They only allow non encrypted traffic
   to work on localhost, so ensure that your remote deployment has a certificate available.
1. To be expanded...
