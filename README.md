# DocWorker: Document Analysis

DocWorker is a Flask web application for running GPT operations over DOCX files.

To run DocWorker, you need an API Key from OpenAI. (Mine came with a $5 credit), and to install various Python modules using pip. Using venv is a good practice.

All commands should be run from the top level of the project directory.

## Installation


`pip install -r docworker/requirements.txt`


## Configure


### Initialize database

`flask --app docworker.analysis_app init-db`

### Add a user

`flask --app docworker.analysis_app set-user <user-name>`

### Lookup access key

`flask --app docworker.analysis_app get-user <user-name>`

## Run Debug Server

`export OPENAI_API_KEY=<key>`

Run the app in debug mode with:

`flask --app docworker.analysis_app run --debug`

Run with OpenAI calls mocked out:

`flask --app "docworker.analysis_app:create_app(fakeai=True)" run --debug`


Open: http://localhost:5000/?authkey=<access_key>

## Test

Run System and Unit tests

`make test`

### Unit test
`make unittest`

### System test
`make systest`

## Run Production Server

Dockworker can be built into a module and installed on a production server,
and run as a wsgi application with a server such as waitress. I have apache2 in front of waitress as a proxy. See the notes.txt file for more information.




