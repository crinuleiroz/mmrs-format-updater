import os, sys, time
import re
import tempfile
import shutil
import zipfile
import unicodedata
import threading, itertools

from typing import Final

import logging

logging.basicConfig(
    filename='conversion_errors.log',
    level=logging.ERROR,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

FILES = sys.argv[1:]

# ANSI Terminal Color Codes
RED        : Final = '\x1b[31m'
PINK_218   : Final = '\x1b[38;5;218m'
PINK_204   : Final = '\x1b[38;5;204m'
YELLOW     : Final = '\x1b[33m'
YELLOW_229 : Final = '\x1b[38;5;229m'
CYAN       : Final = '\x1b[36m'
BLUE_39    : Final = '\x1b[38;5;39m'
GRAY_245   : Final = '\x1b[38;5;245m'
GRAY_248   : Final = '\x1b[38;5;248m'
GREEN_79   : Final = '\x1b[38;5;79m'

BOLD      : Final = '\x1b[1m'
ITALIC    : Final = '\x1b[3m'
UNDERLINE : Final = '\x1b[4m'
STRIKE    : Final = '\x1b[9m'
RESET     : Final = '\x1b[0m'

PL  : Final = '\x1b[F'
CL  : Final = '\x1b[K'

SPINNER_FRAMES : Final[list[str]] = [
  "⢀⠀", "⡀⠀", "⠄⠀", "⢂⠀", "⡂⠀", "⠅⠀", "⢃⠀", "⡃⠀",
  "⠍⠀", "⢋⠀", "⡋⠀", "⠍⠁", "⢋⠁", "⡋⠁", "⠍⠉", "⠋⠉",
  "⠋⠉", "⠉⠙", "⠉⠙", "⠉⠩", "⠈⢙", "⠈⡙", "⢈⠩", "⡀⢙",
  "⠄⡙", "⢂⠩", "⡂⢘", "⠅⡘", "⢃⠨", "⡃⢐", "⠍⡐", "⢋⠠",
  "⡋⢀", "⠍⡁", "⢋⠁", "⡋⠁", "⠍⠉", "⠋⠉", "⠋⠉", "⠉⠙",
  "⠉⠙", "⠉⠩", "⠈⢙", "⠈⡙", "⠈⠩", "⠀⢙", "⠀⡙", "⠀⠩",
  "⠀⢘", "⠀⡘", "⠀⠨", "⠀⢐", "⠀⡐", "⠀⠠", "⠀⢀", "⠀⡀",
]

done_flag = threading.Event()
spinner_thread = threading.Thread()

SEQ_EXTS : Final[tuple[str]] = (
  '.seq',
  '.aseq',
  '.zseq',
)

FANFARE_CATEGORIES : Final[list[str]] = [
  # GROUPS
  '8', '9', '10',
  # INDIVIDUAL
  '108', '109', '119', '120', '121', '122',
  '124', '137', '139', '13D', '13F', '141',
  '152', '155', '177', '178', '179', '17C',
  '17E',
]

def spinner_task(message: str, done_flag: threading.Event) -> None:
  '''Handles the spinner message in the terminal'''
  for frame in itertools.cycle(SPINNER_FRAMES):
    if done_flag.is_set():
      break
    sys.stdout.write(f"{PL}{CL}{PINK_204}{frame}{RESET} {GRAY_245}{message}{RESET}\n")
    sys.stdout.flush()
    time.sleep(0.07)
  sys.stdout.write(f"{PL}{CL}{GREEN_79}✓{RESET} {GRAY_245}{message}{RESET}\n")
  sys.stdout.flush()

def remove_diacritics(text: str) -> str:
  '''Normalizes filenames to prevent errors caused by diacritics'''
  normalized = unicodedata.normalize('NFD', text)
  without_diacritics = ''.join(c for c in normalized if unicodedata.category(c) != 'Mn')

  return without_diacritics

class StandaloneSequence:
  '''Stores and processes standalone sequence file information, also handling unpacking and repacking'''
  def __init__(self, filename, base_folder, tempfolder):
    self.filename = None
    self.instrument_set = None
    self.categories = []

    # Get the paths
    self.basefolder : str = base_folder
    self.tempfolder : str = tempfolder
    self.convfolder : str = os.path.join(self.basefolder, 'converted')

    # Get the metadata from the filename
    self._parse_filename(filename)

  def _parse_filename(self, filename) -> None:
    '''Extracts metadata from sequence file's filename'''
    basename = os.path.basename(filename)
    name_no_ext = basename.replace('.zseq', '')

    parts = name_no_ext.split('_')

    if len(parts) != 3:
      raise ValueError(f'ERROR: Error processing zseq file: {basename}! Too many or too few parameters in filename!')

    self.filename = remove_diacritics(parts[0])
    self.instrument_set = parts[1]
    self.categories = parts[2].split('-')

  def copy(self, filepath) -> None:
    '''Copies sequence file to its tempfolder'''
    if not os.path.isdir(self.convfolder):
      os.mkdir(self.convfolder)

    if os.path.isfile(self.filename + '.zip'):
      os.remove(self.filename + '.zip')

    if os.path.isfile(self.filename + '.mmrs'):
      os.remove(self.filename + '.mmrs')

    with open(filepath, 'rb') as src:
      with open(f'{self.tempfolder}/{self.filename}.seq', 'wb') as dst:
        dst.write(src.read())

  def pack(self, filename, rel_path) -> None:
    '''Packs the temp folder into a new mmrs file'''
    output_path = os.path.join(self.convfolder, os.path.dirname(rel_path))

    if os.path.exists(output_path) and os.path.isfile(output_path):
      os.remove(output_path)

    os.makedirs(output_path, exist_ok=True)

    archive_path = os.path.join(output_path, filename)
    shutil.make_archive(archive_path, 'zip', self.tempfolder)

    mmrs_path = f'{archive_path}.mmrs'
    if os.path.exists(mmrs_path):
      if os.path.isdir(mmrs_path):
        shutil.rmtree(mmrs_path)
      else:
        os.remove(mmrs_path)

    os.rename(f'{archive_path}.zip', f'{archive_path}.mmrs')

class MusicArchive:
  '''Stores packed music file information, also handling unpacking and repacking'''
  def __init__(self, base_folder, tempfolder):
    self.sequences  : list[tuple[str, str]] = [] # (name, extension)
    self.categories : str = None
    self.banks      : dict[str, tuple[str, str]] = {} # { '28': ('28.zbank', '28.bankmeta')}
    self.formmasks  : dict[str, str] = {} # { '28': '28.formmask' }

    # Store zsounds in a dictionary
    self.zsounds : dict[str, str] = {}

    # Get the paths
    self.basefolder : str = base_folder
    self.tempfolder : str = tempfolder
    self.convfolder : str = os.path.join(self.basefolder, 'converted')

  def unpack(self, filename : str, filepath : str) -> None:
    '''Unpacks an mmrs file into its temp directory'''
    if not os.path.isdir(self.convfolder):
      os.mkdir(self.convfolder)

    if os.path.isfile(filename + '.zip'):
      os.remove(filename + '.zip')

    if os.path.isfile(filename + '.mmrs'):
      os.remove(filename + '.mmrs')

    with zipfile.ZipFile(filepath, 'r') as zip_archive:
      zip_archive.extractall(self.tempfolder)

    for f in os.listdir(self.tempfolder):
      # Store sequence(s)
      if f.endswith(SEQ_EXTS):
        base, ext = os.path.splitext(f)
        self.sequences.append((base, ext))
        continue

      # Sore the zbank and bankmeta information
      if f.endswith('.zbank'):
        base = os.path.splitext(f)[0]
        zbank_path = f
        bankmeta_path = f'{base}.bankmeta'

        if os.path.exists(os.path.join(self.tempfolder, bankmeta_path)):
          self.banks[base] = (zbank_path, bankmeta_path)
        else:
          raise FileNotFoundError(f'ERROR: Error processing zbank file: {zbank_path}! Missing bankmeta file!')
        continue

      if f.endswith('.bankmeta'):
        continue

      # Store the categories information
      if f == 'categories.txt':
        self.categories = f
        continue

      # Store the formmask information
      if f.endswith('.formmask'):
        base = os.path.splitext(f)[0]
        self.formmasks[base] = f
        continue

      # Store the zsound information
      if f.endswith('.zsound'):
        split = f.split('.zsound')
        base = split[0]
        split = base.split('_')

        # Ensure the format is correct: name_tempaddr.zsound
        if len(split) != 2:
          raise ValueError(f'ERROR: Error processing zsound file: {f}! Too many or too few parameters in filename!')

        name = split[0]
        temp_addr = split[1]

        os.rename(f'{self.tempfolder}/{f}', f'{self.tempfolder}/{name}.zsound')

        self.zsounds[name] = temp_addr
        continue

    if not self.sequences:
      raise FileNotFoundError(f'ERROR: Error processing mmrs file: {filename}! Missing sequence file!')
    if not self.categories:
      raise FileNotFoundError(f'ERROR: Error processing mmrs file: {filename}! Missing categories file!')

  def pack(self, filename, rel_path) -> None:
    '''Packs the temp folder into a new mmrs file'''
    output_path = os.path.join(self.convfolder, os.path.dirname(rel_path))

    if os.path.exists(output_path) and os.path.isfile(output_path):
      os.remove(output_path)

    os.makedirs(output_path, exist_ok=True)

    archive_path = os.path.join(output_path, filename)
    shutil.make_archive(archive_path, 'zip', self.tempfolder)

    mmrs_path = f'{archive_path}.mmrs'
    if os.path.exists(mmrs_path):
      if os.path.isdir(mmrs_path):
        shutil.rmtree(mmrs_path)
      else:
        os.remove(mmrs_path)

    os.rename(f'{archive_path}.zip', mmrs_path)

def get_files_from_directory(directory: str) -> list[tuple[str, str]]:
  '''Recursively searches a directory to copy its structure'''
  files = []
  for root, _, filenames in os.walk(directory):
    for filename in filenames:
      full_path = os.path.join(root, filename)
      rel_path = os.path.relpath(full_path, start=directory)
      files.append((full_path, rel_path))

  return files

def convert_standalone(file, base_folder, rel_path) -> None:
  '''Processes and converts a zseq into a new mmrs file'''
  cosmetic_name : str = ''
  meta_bank     : str = ''
  song_type     : str = ''
  categories    : str = ''

  filename = os.path.splitext(os.path.basename((remove_diacritics(file))))[0]
  filepath = os.path.abspath(file)

  # Create the temp folder and ensure it deletes itself if an exception occurs
  with tempfile.TemporaryDirectory(prefix='zseq_convert_') as tempfolder:
    standalone = StandaloneSequence(filename, base_folder, tempfolder)

    # Skip already converted files
    if os.path.isfile(f'{archive.convfolder}/{filename}.zseq'):
      return

    # Copy the sequence file to the temp folder
    standalone.copy(filepath)

    cosmetic_name = re.sub(r'\W*(songforce|songtest)\W*', '', filename).strip()
    meta_bank = standalone.instrument_set

    # 0x28 and higher indicate a custom instrument bank
    try:
      if int(meta_bank, 16) > 0x27:
        raise ValueError(f'ERROR: Error processing zseq file: {filename}.zseq! Instrument bank outside valid values!')
    except:
      raise ValueError(f'ERROR: Error processing zseq file: {filename}.zseq! Invalid instrument bank value!')

    # Check for mixed BGM and Fanfare categories
    ff_or_bgm = [category.upper() in FANFARE_CATEGORIES for category in standalone.categories]

    if all(ff_or_bgm):
      song_type = 'fanfare'
    elif not all(ff_or_bgm) and any(ff_or_bgm):
      raise ValueError(f'ERROR: Error processing zseq file: {filename}.zseq! Mixed BGM and Fanfare categories!')
    else:
      song_type = 'bgm'

    categories = ','.join(standalone.categories)

    # Write the meta file
    with open(f'{tempfolder}/{standalone.filename}.meta', 'a') as meta:
      meta.write(cosmetic_name)
      meta.write('\n' + meta_bank)
      meta.write('\n' + song_type)
      meta.write('\n' + categories)

    standalone.pack(standalone.filename, rel_path)

def convert_archive(file, base_folder, rel_path) -> None:
  '''Processes and converts an old mmrs file into a new mmrs file'''
  cosmetic_name : str = ''
  meta_bank     : str = ''
  song_type     : str = ''
  categories          = ''
  zsounds : list[str] = []

  filename = os.path.splitext(os.path.basename((remove_diacritics(file))))[0]
  filepath = os.path.abspath(file)

  # Create the temp folder and ensure it deletes itself if an exception occurs
  with tempfile.TemporaryDirectory(prefix='mmrs_convert_') as tempfolder:
    archive = MusicArchive(base_folder, tempfolder)

    # Skip already converted files
    if os.path.isfile(f'{archive.convfolder}/{filename}.mmrs'):
      return

    try:
      archive.unpack(filename, filepath)
    except:
      raise Exception(f'ERROR: Error processing mmrs file: {filename}.mmrs! Cannot unpack archive!')

    cosmetic_name = re.sub(r'\W*(songforce|songtest)\W*', '', filename).strip()
    original_temp = tempfolder

    # Process the categories file
    with open(f'{tempfolder}/{archive.categories}', 'r') as text:
      categories = text.readline().strip()

      # There are two valid delimiters
      if '-' in categories:
        categories = categories.split('-')
      else:
        try:
          categories = categories.split(',')
        except:
          raise Exception(f'ERROR: Error processing categories file: {filename}.mmrs! Categories cannot be separated!')

      # Check for mixed BGM and Fanfare categories
      ff_or_bgm = [category.upper() in FANFARE_CATEGORIES for category in categories]

      if all(ff_or_bgm):
        song_type = 'fanfare'
      elif not all(ff_or_bgm) and any(ff_or_bgm):
        raise ValueError(f'ERROR: Error processing categories file: {filename}.mmrs! Mixed BGM and Fanfare categories!')
      else:
        song_type = 'bgm'

      categories = ','.join(categories)

    # If there's multiple sequence files, loop through them
    for base_name, ext in archive.sequences:
      # Create a new temp folder for each individual sequence file
      with tempfile.TemporaryDirectory(prefix='mmrs_convert_2_') as song_folder:

        meta_bank = base_name # The instrument set is the name of the sequence

        # Copy sequence file into the temp folder and change its extension to .seq
        original_seq = os.path.join(original_temp, f'{base_name}{ext}')
        new_seq_path = os.path.join(song_folder, f'{base_name}.seq')
        shutil.copy2(original_seq, new_seq_path)

        # Store custom bank related information for meta writing
        # If there's multiple bank files, loop through them
        if base_name in archive.banks:
          zbank, bankmeta = archive.banks[base_name]
          shutil.copy2(os.path.join(original_temp, zbank), song_folder)
          shutil.copy2(os.path.join(original_temp, bankmeta), song_folder)

          meta_bank = '-' # The file uses a custom instrument set

          for item in os.listdir(original_temp):
            if item.endswith('.zsound'):
              shutil.copy2(os.path.join(original_temp, item), song_folder)

          for key, value in archive.zsounds.items():
            if key and value:
              command = f'ZSOUND:{key}.zsound:{value}'
              zsounds.append(command)

        # Copy the formmask file into the temp folder
        if base_name in archive.formmasks:
          formmask = archive.formmasks[base_name]
          shutil.copy2(os.path.join(original_temp, formmask), song_folder)

        # Copy extra non-processed files
        for item in os.listdir(original_temp):
          if item.endswith(('.seq', '.zseq', '.aseq', '.zbank', '.bankmeta', '.zsound', '.formmask')) or item == 'categories.txt':
            continue

          full_item_path = os.path.join(original_temp, item)
          if os.path.isfile(full_item_path):
            shutil.copy2(full_item_path, song_folder)

        # Write the meta file
        with open(os.path.join(song_folder, f'{base_name}.meta'), 'a') as meta:
          meta.write(cosmetic_name)
          meta.write('\n' + meta_bank)
          meta.write('\n' + song_type)
          meta.write('\n' + categories)
          if zsounds:
            for garbage in zsounds:
              meta.write('\n' + garbage)

        temp_archive = MusicArchive(base_folder, song_folder)

        # If there's more than one sequence, ensure each separate file has some identifier of some kind
        if len(archive.sequences) > 1:
          temp_archive.pack(f'{filename}_{base_name}', rel_path)
        else:
          temp_archive.pack(f'{filename}', rel_path)

if __name__ == '__main__':
  def process_file(full_path, base_folder, rel_path) -> None:
    '''Processes files and logs any errors that occur during the processing'''
    global spinner_thread
    try:
      if full_path.endswith('.zseq'):
        convert_standalone(full_path, base_folder, rel_path)
      elif full_path.endswith('.mmrs'):
        convert_archive(full_path, base_folder, rel_path)
    except Exception as e:
      done_flag.set()

      if spinner_thread.is_alive():
          spinner_thread.join()

      print(f"{RED}Error processing {full_path}:{RESET}")
      print(f"{YELLOW}{str(e)}{RESET}")
      logging.error(f"Error processing {full_path}", exc_info=True)

      done_flag.clear()
      spinner_thread = threading.Thread(target=spinner_task, args=("Processing files...", done_flag))
      spinner_thread.start()

  # Let the user know the process is ongoing
  done_flag.clear()
  spinner_thread = threading.Thread(target=spinner_task, args=("Processing files...", done_flag))
  spinner_thread.start()

  try:
    for file in FILES:
      # If the path is a directory, get all files and then process them copying directories
      if os.path.isdir(file):
        base_folder = os.path.abspath(file)
        file_list = get_files_from_directory(base_folder)

        for full_path, rel_path in file_list:
          process_file(full_path, base_folder, rel_path)

      # If the path is a file, process the file directly
      else:
        base_folder = os.path.dirname(os.path.abspath(file))
        rel_path = os.path.basename(file)
        full_path = os.path.abspath(file)

        process_file(full_path, base_folder, rel_path)

  # Let the user know the process is over
  finally:
    done_flag.set()
    spinner_thread.join()

    sys.stdout.write(f"{PL}{CL}{GREEN_79}✓{RESET} {GRAY_245}All files processed.{RESET}\n")
    sys.stdout.flush()

  os.system('pause') # Pause so errors and indication the process is complete are not lost
