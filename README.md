# DocWorker: Document Analysis

DocWorker is a Flask web application for running GPT operations over DOCX files.

All commands should be run from the top level of the project directory.

## Installation

`pip install -r docworker/requirements.txt`


## Configure

### Set OpenAI Key

`export OPENAI_API_KEY=<key>`

### Add a user

`python3 -m docworker.add_user instance/ user-name`


## Run Debug Server

Run the script in debug mode with:

`flask --app docworker.analysis_app run --debug`

Run with OpenAI calls mocked out:

`flask --app "docworker.analysis_app:create_app(fakeai=True)" run --debug`


Open: http://localhost:5000/?authkey=user-name

## Test

### Unit test
`python3 -m unittest docworker/docx_util_test.py`

(more to do here)


