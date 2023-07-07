# DocWorker: Document Analysis

DocWorker is a Flask web application for running GPT operations over DOCX files.

## Installation

mkdir project
cd project
python3 -m venv .venv

. ./venv/bin/activate

`pip install -r docworker/requirements.txt`

Verify installation of flask with `flask --version`


## Configure

OpenAI Key - export 

`export OPENAI_API_KEY=<key>`

python3 -m docworker.add_user instance/ user


## Usage

Run the script in debug mode with:

`cd docworker`
`flask --app "analysis_app:create_app(debug=True)" run --debug`

http://localhost:5000/?authkey=user

## Test

# Unit test
`python3 -m unittest docworker/docx_util_test.py`


## Build

`python3 -m build  --wheel`
`cp dist/docworker-0.1.0-py3-none-any.whl ...`

