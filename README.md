# DocWorker: Document Analysis

DocWorker is a Flask web application for running GPT operations over DOCX files.

## Installation

`cd docworker`
`pip install -r docworker/requirements.txt`


## Configure

### Set OpenAI Key

`export OPENAI_API_KEY=<key>`

### Add a user

`cd docworker
python3 -m docworker.add_user instance/ user-name`


## Run Debug Server

Run the script in debug mode with:

`cd docworker/dockworker
flask --app "analysis_app:create_app(debug=True)" run --debug`

Open: http://localhost:5000/?authkey=user-name

## Test

# Unit test
`python3 -m unittest docworker/docx_util_test.py`
(more to do here)


