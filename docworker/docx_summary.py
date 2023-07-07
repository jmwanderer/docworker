"""
Command line function to work with DOCX file segments and
completions.
"""
import argparse
import os
import openai

from . import docx_util

def start_doc_completion(session_file, session, prompt):
  docx_util.start_docgen(session_file, session, prompt)  

def run_doc_completion(session_file, session):
  print("Running doc completion")
  while  session.status.next_item()is not None:
    item = session.get_item_by_id(session.status.next_item())
    print("Processing: %s" % item.name())
    docx_util.run_next_docgen(session_file, session)
  print("Complete")  


def run_docx_summary():
  parser = argparse.ArgumentParser(description='Completions for a docx file.')
  group = parser.add_mutually_exclusive_group(required=True)
  group.add_argument('--new', metavar='DOCX-file')
  group = group.add_mutually_exclusive_group()
  group.add_argument('--list', action='store_true')
  group.add_argument('--prompts', action='store_true')  
  group.add_argument('--show', metavar='ITEM', nargs='+')
  group.add_argument('--completion', metavar='ITEM', nargs='+')
  group.add_argument('--combined_completion', metavar='ITEM', nargs='+')
  group.add_argument('--start_doc_completion', action='store_true')
  group.add_argument('--run_doc_completion', action='store_true')    
  group.add_argument('--export', action='store_true')
  parser.add_argument('--prompt')
  parser.add_argument('--config')
  parser.add_argument('session_file')  

  args = parser.parse_args()

  if args.config is not None:
    # Read a config file
    if not os.path.exists(args.config):
      print("File %s does not exist." % args.config)
      return
    vars = {}
    config_code = open(args.config).read()
    exec(config_code, vars)
    openai.api_key = vars['OPENAI_API_KEY']    

  if args.new is not None:
    if os.path.exists(args.session_file):
      print('File %s exists' % args.session_file)
      return
    
    session = docx_util.Session()
    file_name = args.new
    file = open(file_name, 'rb')
    print("loading file %s..." % file_name)
    session.load_doc(file_name, file)
    file.close()
    docx_util.save_session(args.session_file, session)
    print("Complete")    
  else:
    print("Loading session: %s" % args.session_file)
    session = docx_util.load_session(args.session_file)

  print(session.name)

  if args.prompts:
    for entry in session.get_prompt_set():
      print(entry[1])

  if args.list:
    token_count = 0
    completion_token_count = 0
    gen_token_count = 0
    print("Document segments:")
    for segment in session.doc_segments:
      print("%s: %s (%d)" % (segment.name(),
                                   session.snippet_text(segment.text()),
                                   segment.token_count()))
      token_count += segment.token_count()
      segment_completion_cost = 0
      for completion in session.completions:
        if completion.match_segment_id(segment.id()):
          print("    %s: [%s] %s (%d)" %
                (completion.name(),
                 session.get_prompt_name_by_id(completion.prompt_id),
                 session.snippet_text(completion.text()),
                 completion.token_count()))
          completion_token_count += completion.token_count()
          segment_completion_cost += completion.token_cost          

      if (segment_completion_cost > 0):
        print("   Generation cost %d tokens" % segment_completion_cost)
      gen_token_count += segment_completion_cost
      print()

    print("Generated:")
    for completion in session.completions:
      if completion.doc_segment_name() is None:
        print("    %s: [%s] %s (%d)" %
              (completion.name(),
               session.get_prompt_name_by_id(completion.prompt_id),
               session.snippet_text(completion.text()),
               completion.token_count()))
        completion_token_count += completion.token_count()
      
    print("Total token counts: text = %d, completion = %d, generation = %d" %
          (token_count, completion_token_count, gen_token_count))

  if args.show is not None:
    for name in args.show:
      item = session.get_item_by_name(name)
      if (item is None):
        print("Item %s not found" % name)
        continue

      if (item.is_doc_segment()):
        print("section %s" % item.name())
        print(item.text())
      else:
        print("%s: Prompt: %s [ %s ]" %
              (item.name(),
               item.prompt(session),
               session.get_names_for_ids(item.input_ids)))
        print(item.text())

  if args.start_doc_completion:
    if args.prompt is None:
      print("Start completion requires a prompt")
      return
    prompt = args.prompt
    start_doc_completion(args.session_file, session, prompt)

  if args.run_doc_completion:
    run_doc_completion(args.session_file, session)
    
  if args.completion is not None:
    for name in args.completion:
      item = session.get_item_by_name(name)
      if (item is None):
        print("Item %s not found" % name)
        continue

      if args.prompt is None:
        print("Completion requires a prompt")
        return

      prompt = args.prompt
      prompt_id = session.get_prompt_id(prompt)
      print("Running [%s] on %s" % (prompt, name))

      (text,
       token_count,
       cost) = docx_util.run_completion(prompt, item.text())
      
      completion = session.add_new_completion(prompt_id, [ item.id() ],
                                              text, token_count, cost)
      docx_util.save_session(args.session_file, session)
      print("Generated: %s" % completion.name())
      print()

  if args.combined_completion is not None:
    input = []
    input_ids = []
    if args.prompt is None:
      print("Completion requires a prompt")
      return
    
    for name in args.combined_completion:
      item = session.get_item_by_name(name)
      if (item is None):
        print("Item %s not found" % name)
        return
      input.append(item.text())
      input_ids.append(item.id())      


    prompt = args.prompt
    prompt_id = session.get_prompt_id(prompt)
      
    print("Running [%s] on [ %s ]" % (prompt,
                                      ' '.join(args.combined_completion)))

    text = '\n'.join(input)

    (text, token_count, cost) = docx_util.run_completion(prompt, text)
    completion = session.add_new_completion(prompt_id, input_ids,
                               text, token_count, cost)
    docx_util.save_session(args.session_file, session)      
    print("Generated: %s" % completion.name())

  if args.export:
    token_count = 0
    prompt_id = session.get_prompt_id_by_name(args.prompt)    
    if prompt_id is None:
      print("Prompt %s is not found" % args.prompt)
    print("Export completions for '%s'" % args.prompt)

    for completion in session.completions:
      if completion.prompt_id == prompt_id:
        print("Item %s from items [ %s ]" %
              (completion.name(),
               session.get_names_for_ids(completion.input_ids)))
        print(completion.text())
        print()
      token_count += completion.token_cost
    print("Total generation cost %d tokens" % token_count)

      

if __name__ == "__main__":
  run_docx_summary()






