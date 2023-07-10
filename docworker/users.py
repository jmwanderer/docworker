import os
import os.path
import sys
import shutil
import pkg_resources
import docworker


def add_user(dir_name, user_name):
  """
  Create a user directory and populate with samples
  """
  user_dir = os.path.join(dir_name, user_name)
  print("user dir = %s" % user_dir)
  samples_dir = pkg_resources.resource_filename('docworker', 'samples')
  print("samples dir = %s" % samples_dir)  
  if not os.path.exists(samples_dir):
    print("%s not found" % samples_dir)

  if not os.path.exists(user_dir):    
    os.makedirs(user_dir)
  for filename in os.listdir(samples_dir):
    if filename.endswith(".daf"):
      shutil.copyfile(os.path.join(samples_dir, filename),
                      os.path.join(user_dir, filename))
  print("done")
  

    

