import os
import os.path
import io
import time
import functools
from threading import Thread
import flask
from flask import Flask
from flask import request
from flask import abort
from flask import render_template, url_for, redirect
from flask import Blueprint, g, current_app, session
from markupsafe import escape
from werkzeug.middleware.proxy_fix import ProxyFix
import werkzeug.utils
from logging.config import dictConfig
import logging
from . import doc_convert
from . import prompts
from . import document
from . import doc_gen
from . import analysis_util
from . import users
import openai
import sqlite3
import click


def create_app(test_config=None,
               fakeai=False,
               instance_path=None):
  BASE_DIR = os.getcwd()
  log_file_name = os.path.join(BASE_DIR, 'docworker.log.txt')
  FORMAT = '%(asctime)s:%(levelname)s:%(name)s:%(message)s'
  if instance_path is None:
    app = Flask(__name__, instance_relative_config=True)
  else:
    app = Flask(__name__, instance_relative_config=True,
                instance_path=instance_path)
    
  app.config.from_mapping(
    SECRET_KEY='DEV',
    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY'),
    MAX_CONTENT_LENGTH = 16 * 1000 * 1000,
    DATABASE=os.path.join(app.instance_path, 'docworker.sqlite'),
    SMTP_USER = os.getenv('SMTP_USER'),
    SMTP_PASSWORD = os.getenv('SMTP_PASSWORD'),        
    SMTP_SERVER = os.getenv('SMTP_SERVER'),
    SMTP_FROM = os.getenv('SMTP_FROM'),        
  )
  if test_config is None:
    app.config.from_pyfile('config.py', silent=True)
  else:
    app.config.from_mapping(test_config)

  if not app.debug:
    # Configure logging
    logging.basicConfig(filename=log_file_name,
                        level=logging.INFO,
                        format=FORMAT,)
  else:
    logging.basicConfig(level=logging.INFO)
  
  doc_gen.FAKE_AI_COMPLETION=fakeai

  # If so configured, setup for running behind a reverse proxy.
  if app.config.get('PROXY_CONFIG'):
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1,
                            x_host=1, x_prefix=1)
    logging.info("set proxy fix")

  try:
    logging.info("instance path = %s", app.instance_path)
    os.makedirs(app.instance_path)
  except OSError:
    pass

  openai.api_key = app.config['OPENAI_API_KEY']

  app.register_blueprint(bp)

  @app.errorhandler(Exception)
  def handle_exception(e):
    logging.exception("Internal error")
    return e

  app.teardown_appcontext(close_db)

  @app.route('/favicon.ico')
  def favicon():
    return redirect(url_for('static', filename='favicon.ico'))
  return app


def get_db():
  if 'db' not in g:
    g.db = sqlite3.connect(
      current_app.config['DATABASE'],
      detect_types=sqlite3.PARSE_DECLTYPES)
    g.db.row_factory = sqlite3.Row
  return g.db

def close_db(e=None):
  db = g.pop('db', None)
  if db is not None:
    db.close()

def init_db():
  db = get_db()
  with current_app.open_resource('schema.sql') as f:
    db.executescript(f.read().decode('utf8'))


bp = Blueprint('analysis', __name__, cli_group=None)
    
@bp.cli.command('init-db')
def init_db_command():
  """Drop and recreate tables."""
  init_db()
  click.echo('Initialized database.')

@bp.cli.command('set-user')
@click.argument('name')
@click.argument('limit', default=100000)
def set_user_command(name, limit):
  """Create or update a user."""
  user_dir = os.path.join(current_app.instance_path, name)
  users.add_or_update_user(get_db(), user_dir, name, limit)
  click.echo('Configured user.')

@bp.cli.command('set-user-key')
@click.argument('name')
@click.argument('key')
def set_user_command(name, key):
  """Update an access key for a user."""
  users.set_user_key(get_db(), name, key)
  click.echo('Updated user.')

@bp.cli.command('get-user')
@click.argument('name')
def get_user_command(name):
  """Dump details of given user."""
  users.report_user(get_db(), name)

@bp.cli.command('list-users')
def list_command():
  """List the users in the DB."""
  users.list_users(get_db())

  
def get_doc_file_path(doc_name):
  """
  Given a document name, return the path to the pickle doc 
  on the local storage.
  """
  file_name = doc_name + '.daf'
  return os.path.join(current_app.instance_path, g.user, file_name)
  

def get_document(doc_name):
  """
  Load a document for the given doc name.
  If the name is None, or the session can not be loaded, return None
  """
  if doc_name is None:
    return None
  
  file_path = get_doc_file_path(doc_name)
  if not os.path.exists(file_path):
    return None
  doc = document.load_document(file_path)
  return doc

    
@bp.before_app_request
def load_logged_in_user():
  user_key = session.get('user_key')
  g.user = None
  # Validate user_key
  if user_key is not None and len(user_key) > 0:
    user_name = users.get_user_by_key(get_db(), user_key)
    if user_name is not None:
      g.user = user_name
      users.note_user_access(get_db(), user_name)

def login_required(view):
  @functools.wraps(view)
  def wrapped_view(**kwargs):
    if g.user is None:
      return redirect(url_for('analysis.login'))
    return view(**kwargs)
  return wrapped_view

def set_logged_in_user(user_name):
  # For testing
  g.user = user_name

def handle_login(request):
  """
  Process login steps.
  Return None to proceed, a redirect otherwise.
  """
  # Handle initial authorization
  auth_key = request.args.get("authkey")
  if auth_key is not None:
    user_name = users.get_user_by_key(get_db(), auth_key)
    if user_name is not None:
      session.permanent = True
      session['user_key'] = auth_key
    else:
      session.permanent = False      
      session['user_key'] = None
    return redirect(url_for('analysis.main'))
  
  load_logged_in_user()
  if g.user is None:
    return redirect(url_for('analysis.login'))    
  return None


@bp.route("/", methods=("GET","POST"))
def main():
  # Check and process login if needed
  login_redirect = handle_login(request)
  if login_redirect is not None:
    return login_redirect
  
  doc = None
  if request.method == "GET":  
    doc_id = request.args.get('doc')
    run_id = request.args.get('run_id')
    if run_id != None:
      run_id = int(run_id)
    doc  = get_document(doc_id)
    prompts_set = prompts.Prompts.get_initial_prompt_set()
    if doc is not None:
      # If a run is in progress, show that run
      if run_id is None and doc.is_running():
        run_id = doc.get_current_run_record().run_id
      prompts_set = doc.prompts.get_prompt_set()

    return render_template("main.html",
                           doc=doc,
                           username=g.user,
                           run_id=run_id,
                           prompts=prompts_set)

  else:
    doc_id = request.form.get('doc')
    
    if request.form.get('upload'):
      if ('file' not in request.files or
          request.files['file'].filename == ''):
        return redirect(url_for('analysis.main'))

      file = request.files['file']
      filename = werkzeug.utils.secure_filename(file.filename)
      user_dir = os.path.join(current_app.instance_path, g.user)

      doc_id = None
      try:    
        doc_id = document.find_or_create_doc(user_dir, filename, file)
      except doc_convert.DocError as err:
        flask.flash("Error loading file: %s" % str(err))

      return redirect(url_for('analysis.main', doc=doc_id))

    elif request.form.get('run'):
      prompt = request.form['prompt'].strip()      
      doc = get_document(doc_id)
      if (doc is None or doc.is_running() or
          prompt is None or len(prompt) == 0):
        return redirect(url_for('analysis.main'))
      
      logging.info("Start doc run")
      file_path = get_doc_file_path(doc_id)
      run_state = doc_gen.start_docgen(file_path, doc, prompt)
      
      # Check if there are clearly not  enough tokens to run the generation
      if (doc_gen.run_input_tokens(doc, run_state) >
          users.token_count(get_db(), g.user)):
          doc.mark_cancel_run("Insufficient tokens")
          document.save_document(file_path, doc)
      else:
        t = Thread(target=background_docgen,
                   args=[current_app.config['DATABASE'], g.user,
                         file_path, doc, run_state])
        t.start()
        
      return redirect(url_for('analysis.main', doc=doc.id(), run_id=run_state.run_id))

    else:
      return redirect(url_for('analysis.main', doc=doc.id()))
  
def background_docgen(db_config, username, file_path, doc, run_state):
  """
  Runs from a background thread to process the document and 
  update the consumed token accouting.
  """
  # Open database
  db = sqlite3.connect(db_config, detect_types=sqlite3.PARSE_DECLTYPES)
  db.row_factory = sqlite3.Row

  id = doc_gen.run_all_docgen(file_path, doc, run_state)
  if id is not None:
    family = doc.get_completion_list(run_state.run_id)
    tokens = sum(item.token_cost for item in family)
    users.increment_tokens(db, username, tokens)
    logging.info("updated cost for %s of %d tokens", username, tokens)
  
  # Close database
  db.close()


@bp.route("/doclist", methods=("GET",))
@login_required
def doclist():
  user_dir = os.path.join(current_app.instance_path, g.user)  
  file_list = []
  for filename in os.listdir(user_dir):
    if filename.endswith('.daf'):
      file_list.append(filename[:-4]) 
  return render_template("doclist.html", files=file_list)
  


@bp.route("/runlist", methods=("GET",))
@login_required
def runlist():
  doc_id = request.args.get('doc')  
  doc = get_document(doc_id)
  if doc is None:
    return redirect(url_for('analysis.main'))
  return render_template("runlist.html", doc=doc)

    
@bp.route("/segview", methods=("GET",))
@login_required
def segview():
  doc_id = request.args.get('doc')
  doc = get_document(doc_id)  
  if doc is None:
    return redirect(url_for('analysis.main'))

  run_id = request.args.get('run_id')
  item_name = request.args.get("item")
  item = doc.get_item_by_name(run_id, item_name)  
  if run_id is None or item is None:
    return redirect(url_for('analysis.main', doc=doc_id))
  
  # Source items for a completion (returns empty for docseg)
  (depth, item_list) = doc.get_completion_family(run_id, item.id())
  # Remove first item
  if (len(item_list) > 0):
    item_list.pop(0)

  # Generate next and prev items
  next_item = None
  prev_item = None
  ordered_list = []
  
  (x, list) = doc.get_completion_family(run_id)
  ordered_items = [ x[1] for x in list ]
      
  if item in ordered_items:
    item_index = ordered_items.index(item)
    if item_index > 0:
      prev_item = ordered_items[item_index - 1]
    if item_index < len(ordered_items) - 1:
      next_item = ordered_items[item_index + 1]
  
  return render_template("segview.html",
                         doc=doc,
                         run_id=run_id,
                         depth=depth,
                         source_list=item_list,
                         item=item, prev_item=prev_item, next_item=next_item)


          
@bp.route("/export", methods=("POST",))
@login_required          
def export():
  doc_id = request.form.get('doc')
  run_id = request.form.get('run_id')    
  doc = get_document(doc_id)
  item_names = request.form.getlist('items')
  if doc is None:
    return redirect(url_for('analysis.main'))
    
  out_file = io.BytesIO()
  if run_id is None:
    # Export document test
    out_file.write(doc.get_doc_text().encode('utf-8'))
  else:
    # Export items from run_id record
    for name in item_names:
      out_file.write(doc.get_item_by_name(run_id, name).text().encode('utf-8'))
      out_file.write('\n\n'.encode('utf-8'))      

  out_file.seek(0, 0)    
  return flask.send_file(out_file, mimetype='text/plain;charset=utf-8',
                         as_attachment=True,
                         download_name='%s.txt' %
                         os.path.basename(doc.name()))

  
  

EMAIL_TEXT = """
Hello %s,

Your access link for DocWorker is %s?authkey=%s

If you didn't request this email, don't worry, your email address
may have been entered by mistake. You can ingore and delete this email.

"""

  
@bp.route("/login", methods=("GET", "POST"))
def login():
  if request.method == "GET":
    status = request.args.get('status')
    return render_template("login.html", status=status)
  else:
    # TODO:
    # - track emails per time unit - rate limit
    # - track emails to target address - limit by time
    # - limit number of accounts
    address = escape(request.form.get('address'))
    status = "unknown"
    key = users.get_user_key(get_db(), address)
    if key is None:
      # User does not exist. Create if we are not at max
      if users.count_users(get_db()) >= users.MAX_ACCOUNTS:
        status = "User limit hit. No more available at this time."
      else:
        # Create the user entry.
        user_dir = os.path.join(current_app.instance_path, address)
        users.add_or_update_user(get_db(), user_dir,
                                 address, users.DEFAULT_TOKEN_COUNT)
        key = users.get_user_key(get_db(), address)

    if key is not None:
      email = EMAIL_TEXT % (address,
                            url_for('analysis.main', _external=True),
                            key)
      logging.info("Login request for %s, result == %s", address, key)

      if users.check_allow_email_send(get_db(), address):
        try:
          analysis_util.send_email(current_app.config, [address],
                                   "Access Link for DocWorker", email)
          status = "Email sent to: %s" % address
          users.note_email_send(get_db(), address)

        except Exception as e:
          logging.info("Failed to send email %s", str(e))
          status = "Email send failed"

      else:
        status = "Email already recently sent to %s" % address
      
    return redirect(url_for('analysis.login', status=status))      

if __name__ == "__main__":
  app = create_app()
  app.run(debug=True)
  
