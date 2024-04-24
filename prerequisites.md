# Prerequisites

## MySQL

In order to store user and organisation data we utilize MySQL. 

## Redis
Please make sure to follow official documentation for installing Redis on your distribution of choice. Below is a general guide.
Also note that when deploying with the supplied docker stack files they also deploy a redis instance.
### On Linux:
1. Ubuntu/Debian:
```
sudo apt update
sudo apt install redis-server
```
2. CentOS/RedHat
```
sudo yum install epel-release
sudo yum install redis
sudo systemctl start redis
sudo systemctl enable redis
```
3. On macOS:
```
brew install redis
```
## Obtain API Keys and Credentials

1. Obtain a Pinecone API key from [Pinecone's portal](https://app.pinecone.io/organizations/).
2. Acquire an OpenAI API key through [OpenAI's platform](https://platform.openai.com/api-keys). 
3. Generate Google OAuth credentials via [Google Cloud Console](https://console.cloud.google.com/apis/credentials).

## Configuration variables 

In order to pass these keys, connection strings for the MySQL database etc you have two options:

### JSON settings file
*Note this option is a bit more difficult to pull of with a container, since you need to ensure the file doesn't get overwritten on new image deploy*

The [example settings](./settings.json.example) file contains examples of all 

## Env vars

You can export the following env vars either through Docker or your local shell.

```
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
Note that the project id is the id of the project in the [google console](https://console.cloud.google.com/cloud-resource-manager). All of the GOOGLE_ prepended ones are available there actually. 

## non-local-deploy

When deploying to remote-accessible environments you need to make a couple of considerations:

1. The Redirect URI used for Google Oauth needs to be https. They only allow non encrypted traffic to work on localhost, so ensure that your remote deployment has a certificate available.
2. To be expanded...
