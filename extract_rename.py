# extract the files to a folder above and renames them to the workshop name
# WARNING, multiple files with the same extension will be overidden
import os

new_path = os.path.join(PATH, '..')
for file in os.listdir(PATH):
    filepath = os.path.join(PATH, file)
    if os.path.isfile(filepath):
        basename, ext = os.path.splitext(filepath)
        os.rename(os.path.join(filepath), os.path.join(new_path, NAME+ext))
os.rmdir(PATH)
