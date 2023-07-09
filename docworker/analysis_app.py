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
from . import docx_summary
from . import docx_util
from . import analysis_util
import openai
import sqlite3
import click


def create_app(test_config=None,fakeai=False):
  BASE_DIR = os.getcwd()
  log_file_name = os.path.join(BASE_DIR, 'docworker.log.txt')
  FORMAT = '%(asctime)s:%(levelname)s:%(name)s:%(message)s'
  app = Flask(__name__, instance_relative_config=True)
  app.config.from_mapping(
    SECRET_KEY='DEV',
    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY'),
    MAX_CONTENT_LENGTH = 16 * 1000 * 1000,
    DATABASE=os.path.join(app.instance_path, 'docworker.sqlite'),    
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
    logging.basicConfig(level=logging.DEBUG)
  
  docx_util.FAKE_AI_COMPLETION=fakeai

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
  db = get_db()
  (count,) = db.execute("SELECT COUNT(*) FROM user WHERE username = ?",
                     (name,)).fetchone()
  print("count %d" % count)
  if count == 0:
    print("add user")
    db.execute("INSERT INTO user (username, limit_tokens) VALUES (?,?)",
               (name, limit))
  else:
    db.execute("UPDATE user SET limit_tokens = ? WHERE username = ?",
               (limit,name))
  db.commit()
  click.echo('Configured user.')

@bp.cli.command('list-users')
def list_command():
  """List the users in the DB."""
  db = get_db()  
  q = db.execute("SELECT username, consumed_tokens, limit_tokens, datetime(last_access, 'unixepoch') FROM user")
  for (user, consumed, limit, last_access) in q.fetchall():
    print("user: %s, limit: %d, consumed %d, last access: %s" %
          (user, limit, consumed, last_access))
    

def get_doc_file_path(doc_name):
  file_name = doc_name + '.daf'
  return os.path.join(current_app.instance_path, g.user, file_name)
  
def get_session(doc_name):
  """
  Load a session for the given doc name.
  If the name is None, or the session can not be loaded, return None
  """
  if doc_name is None:
    return None
  
  file_path = get_doc_file_path(doc_name)
  if not os.path.exists(file_path):
    return None
  
  session = docx_util.load_session(file_path)
  return session

    
@bp.before_app_request
def load_logged_in_user():
  user_key = session.get('user_key')
  g.user = None
  # Validate user_key
  if user_key is not None and len(user_key) > 0:
    user_dir = os.path.join(current_app.instance_path, user_key)      
    if os.path.exists(user_dir):
      g.user = user_key

def login_required(view):
  @functools.wraps(view)
  def wrapped_view(**kwargs):
    if g.user is None:
      return redirect(url_for('static', filename='noauth.html'))
    return view(**kwargs)
  return wrapped_view


@bp.route("/main", methods=("GET","POST"))
@login_required
def main():
  doc = None
  doc_name = None
  print("main")
  if request.method == "GET":  
    doc_id = request.args.get('doc')  
    session = get_session(doc_id)
    if session is not None:
      doc_name=escape(os.path.basename(session.name))
      doc_name=session.name      
      doc = doc_id
                    
    return render_template("main.html",
                           doc=doc,
                           prompts=docx_util.INITIAL_PROMPTS,
                           session=session)

  else:
    doc_id = request.form.get('doc')
    
    if request.form.get('upload'):
      if ('file' not in request.files or
          request.files['file'].filename == ''):
        flask.flash("No file selected.")
        return redirect(url_for('analysis.main'))

      file = request.files['file']
      filename = werkzeug.utils.secure_filename(file.filename)
      user_dir = os.path.join(current_app.instance_path, g.user)

      doc = None
      try:    
        doc = docx_util.find_or_create_doc(user_dir, filename, file)
      except Exception as err:
        flask.flash("Error loading file. (Internal error: %s)" % str(err))      
        flask.flash("Upload a DOCX file.")      

      return redirect(url_for('analysis.main', doc=doc))

    elif request.form.get('run'):
      prompt = request.form['prompt'].strip()      
      session = get_session(doc_id)
      if (session is None or session.status.is_running() or
          prompt is None or len(prompt) == 0):
        return redirect(url_for('analysis.main'))
      
      print("start run prompt")
      file_path = get_doc_file_path(doc_id)
      docx_util.start_docgen(file_path, session, prompt)
      t = Thread(target=docx_util.run_all_docgen,
                 args=[file_path, session])
      t.start()
      return redirect(url_for('analysis.main', doc=doc_id))

    else:
      return redirect(url_for('analysis.main', doc=doc_id))
  


@bp.route("/", methods=("GET",))
def doclist():
  # Handle initial authorization
  auth_key = request.args.get("authkey")
  if auth_key is not None:
    # TODO: validate auth_key
    user_dir = os.path.join(current_app.instance_path, auth_key)
    if os.path.exists(user_dir):
      session.permanent = True
      session['user_key'] = auth_key
    else:
      session.permanent = False      
      session['user_key'] = None
  load_logged_in_user()
  if g.user is None:  
    return redirect(url_for('static', filename='noauth.html'))

  user_dir = os.path.join(current_app.instance_path, g.user)  
  file_list = []
  for filename in os.listdir(user_dir):
    if filename.endswith('.daf'):
      file_list.append(filename[:-4]) 
  return render_template("doclist.html", files=file_list)
  

@bp.route("/upload", methods=("POST",))
@login_required
def upload():
  if ('file' not in request.files or
      request.files['file'].filename == ''):
    flask.flash("No selected file")
    return redirect(url_for('analysis.doclist'))

  file = request.files['file']
  filename = werkzeug.utils.secure_filename(file.filename)
  filename = analysis_util.get_new_filename(filename, g.user)
  if filename is None:
    flask.flash("Unable to handle filename.")      
    return redirect(url_for('analysis.doclist'))  

  file_path = get_doc_file_path(filename)

  session = docx_util.Session()
  try:
    session.load_doc(filename, file)
    docx_util.save_session(file_path, session)
    flask.flash("Loaded new file: " +
                escape(os.path.basename(session.name)))                  
  except Exception as err:
    flask.flash("Error loading file. (Internal error: %s)" % str(err))      
    flask.flash("Upload a DOCX file.")      

  return redirect(url_for('analysis.doclist'))

    
@bp.route("/docview", methods=("GET",))
@login_required
def docview():
  doc = request.args.get('doc')  
  session = get_session(doc)
  if session is None:
    return redirect(url_for('analysis.doclist'))
  
  item_names = request.args.getlist("items")
  focus_item = request.args.get("focus")    

  return render_template("docview.html",
                         doc_name=escape(os.path.basename(session.name)),
                         doc=doc,
                         session=session)

@bp.route("/segview", methods=("GET",))
@login_required
def segview():
  doc = request.args.get('doc')
  session = get_session(doc)  
  if session is None:
    return redirect(url_for('analysis.doclist'))

  item_name = request.args.get("item")
  if item_name is None:
    return redirect(url_for('analysis.docview', doc=doc))
  item = session.get_item_by_name(item_name)
  if item is None:
    return redirect(url_for('analysis.docview', doc=doc))
  
  # Source items for a completion (returns empty for docseg)
  (depth, item_list) = session.get_completion_family(item.id())
  # Remove first item
  if (len(item_list) > 0):
    item_list.pop(0)

  # Generate next and prev items
  next_item = None
  prev_item = None
  ordered_items = session.get_ordered_items()
  if item in ordered_items:
    item_index = ordered_items.index(item)
    if item_index > 0:
      prev_item = ordered_items[item_index - 1]
    if item_index < len(ordered_items) - 1:
      next_item = ordered_items[item_index + 1]
  else:
    logging.error("problem with ordered list gen for item %s" % item.name)
  
  return render_template("segview.html",
                         doc_name=escape(os.path.basename(session.name)),
                         doc=doc,
                         depth=depth,
                         source_list=item_list,
                         item=item, prev_item=prev_item, next_item=next_item,
                         session=session)


@bp.route("/docgen", methods=("GET","POST"))
@login_required
def docgen():
  if request.method == "GET":
    doc = request.args.get('doc')  
    session = get_session(doc)      
    if session is None:
      return redirect(url_for('analysis.doclist'))

    if session.status.is_running():
      # Go to in progress run
      return redirect(url_for('analysis.genresult', doc=doc))          
      
    return render_template("docgen.html",
                           doc_name=escape(os.path.basename(session.name)),
                           doc=doc,
                           session=session)
  else:
    doc = request.form.get('doc')
    session = get_session(doc)          
    if session is None:
      return redirect(url_for('analysis.doclist'))
    file_path = get_doc_file_path(doc)    
    
    prompt = request.form['prompt'].strip()
    if (prompt is None or len(prompt) == 0 or
        session.status.is_running()):
      return redirect(url_for('analysis.docgen', doc=doc))

    docx_util.start_docgen(file_path, session, prompt)
    t = Thread(target=docx_util.run_all_docgen,
               args=[file_path, session])
    t.start()

    return redirect(url_for('analysis.genresult', doc=doc))    
  

@bp.route("/generate", methods=("GET","POST"))
@login_required
def generate():
  if request.method == "GET":
    doc = request.args.get('doc')
    session = get_session(doc)              
    if session is None:
      return redirect(url_for('analysis.doclist'))

    item_names = request.args.getlist("items")
    items_state = analysis_util.ItemsState()
    items_state.set_state(session, item_names)


    return render_template("generate.html",
                           doc_name=escape(os.path.basename(session.name)),
                           doc=doc,
                           items_state=items_state,
                           session=session)
  
  else:
    doc = request.form.get('doc')    
    session = get_session(doc)                  
    if session is None:
      return redirect(url_for('analysis.doclist'))
    file_path = get_doc_file_path(doc)    

    item_names = request.form.getlist('items')
    prompt = request.form['prompt'].strip()

    items_state = analysis_util.ItemsState()    
    items_state.set_state(session, item_names)
  
    id_list = []
    for item_name in items_state.selected_names():
      item = session.get_item_by_name(item_name)
      if item is not None:
        id_list.append(item.id())

    if (prompt is None or len(prompt) == 0 or len(id_list) == 0 or
        session.status.is_running()):
      return redirect(url_for('analysis.generate', doc=doc, items=item_names))
        
    prompt_id = session.get_prompt_id(prompt)
  
    docx_util.start_docgen(file_path, session, prompt, id_list)
    t = Thread(target=docx_util.run_all_docgen,
               args=[file_path, session])
    t.start()

    return redirect(url_for('analysis.genresult', doc=doc))


@bp.route("/genresult")
@login_required
def genresult():
  doc = request.args.get('doc')
  session = get_session(doc)              
  if session is None:
    return redirect(url_for('analysis.doclist'))

  return render_template("genresult.html",
                         doc_name=escape(os.path.basename(session.name)),
                         doc=doc,
                         session=session)
  
@bp.route("/dispatch")
@login_required          
def dispatch():
    doc = request.args.get('doc')
    item_names = request.args.getlist("items")
          
    if request.args.get('ProcessDoc'):
      return redirect(url_for('analysis.docgen',
                              doc=doc, items=item_names))              

    if request.args.get('ProcessBlocks'):
      return redirect(url_for('analysis.sel_gen',
                              doc=doc, items=item_names))              

    if request.args.get('ExportBlocks'):
      return redirect(url_for('analysis.sel_export', doc=doc))

    return redirect(url_for('analysis.docview',
                            doc=doc, items=item_names))              
          
@bp.route("/export", methods=("GET", "POST"))
@login_required          
def export():
  if request.method == "GET":    
    doc = request.args.get('doc')
    session = get_session(doc)                      

    item_names = request.args.getlist("items")
    items_state = analysis_util.ItemsState()
    items_state.set_state(session, item_names)

    return render_template("export.html",
                           doc_name=escape(os.path.basename(session.name)),
                           doc=doc,
                           items_state=items_state,
                           session=session)
  else:
    doc = request.form.get('doc')
    session = get_session(doc)                          
    item_names = request.form.getlist('items')
    
    out_file = io.BytesIO()
    for name in item_names:
      out_file.write(session.get_item_by_name(name).text().encode('utf-8'))
      out_file.write('\n\n'.encode('utf-8'))      
    out_file.seek(0, 0)
    return flask.send_file(out_file, mimetype='text/plain',
                           as_attachment=True,
                           download_name='%s.txt' %
                           os.path.basename(session.name))


@bp.route("/sel_export", methods=("GET", "POST"))
@login_required          
def sel_export():
  if request.method == "GET":    
    doc = request.args.get('doc')
    session = get_session(doc)                      

    item_id = request.args.get("item")    
    item_names = request.args.getlist("items")
    items_state = analysis_util.ItemsState()
    items_state.set_state(session, item_names)

    depth = 0
    item_list = None
    if item_id is not None:
      (depth, item_list) = session.get_completion_family(int(item_id))

    action="Select items for export."
    return render_template("select.html",
                           doc_name=escape(os.path.basename(session.name)),
                           doc=doc,
                           action=action,
                           depth=depth,
                           item_list=item_list,
                           items_state=items_state,                           
                           page='analysis.sel_export',
                           session=session)
  else:
    doc = request.form.get('doc')
    item_names = request.form.getlist('items')
    if request.form.get('donebutton'):        
      return redirect(url_for('analysis.export', doc=doc, items=item_names))
    return redirect(url_for('analysis.docview', doc=doc))      
  
  
@bp.route("/sel_gen", methods=("GET", "POST"))
@login_required          
def sel_gen():
  if request.method == "GET":    
    doc = request.args.get('doc')
    session = get_session(doc)

    if session.status.is_running():
      # Go to in progress run
      return redirect(url_for('analysis.genresult', doc=doc))          
    
    item_id = request.args.get("item")    
    item_names = request.args.getlist("items")
    items_state = analysis_util.ItemsState()
    items_state.set_state(session, item_names)

    depth = 0
    item_list = None
    if item_id is not None:
      (depth, item_list) = session.get_completion_family(int(item_id))

    action="Select individual items for GPT processing."    
    return render_template("select.html",
                           doc_name=escape(os.path.basename(session.name)),
                           doc=doc,
                           action=action,
                           depth=depth,
                           item_list=item_list,
                           items_state=items_state,
                           page='analysis.sel_gen',
                           session=session)
  else:
    doc = request.form.get('doc')
    item_names = request.form.getlist('items')
    if request.form.get('donebutton'):    
      return redirect(url_for('analysis.generate', doc=doc, items=item_names))
    return redirect(url_for('analysis.docview', doc=doc))      
  

if __name__ == "__main__":
  app = create_app()
  app.run(debug=True)
  
