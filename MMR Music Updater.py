import os, sys, time
import re
import tempfile
import shutil
import zipfile
import unicodedata
import threading, itertools
import yaml

from typing import Final

import logging

logging.basicConfig(
    filename='mmr-music-updater_errors.log',
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

FANFARE_CATEGORIES : Final[list[int]] = [
  # GROUPS
  0x8, 0x9, 0x10,
  # INDIVIDUAL
  0x108, 0x109, 0x119, 0x120, 0x121, 0x122,
  0x124, 0x137, 0x139, 0x13D, 0x13F, 0x141,
  0x152, 0x155, 0x177, 0x178, 0x179, 0x17C,
  0x17E,
]

def spinner_task(message: str, done_flag: threading.Event) -> None:
    for frame in itertools.cycle(SPINNER_FRAMES):
        if done_flag.is_set():
            break
        sys.stderr.write(f"{PL}{CL}{PINK_204}{frame}{RESET} {GRAY_245}{message}{RESET}\n")
        sys.stderr.flush()
        time.sleep(0.07)
    sys.stderr.write(f"{PL}{CL}{GREEN_79}✓{RESET} {GRAY_245}{message}{RESET}\n")
    sys.stderr.flush()

def start_spinner(message: str):
    done_flag.clear()
    thread = threading.Thread(target=spinner_task, args=(message, done_flag))
    thread.start()
    return thread


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
    self.categories : int = []

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
    self.categories = [int(c) for c in parts[2].split('-')]

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
    self.zsounds : dict[str, int] = {}

    # Get the paths
    self.basefolder : str = base_folder
    self.tempfolder : str = tempfolder
    self.convfolder : str = os.path.join(self.basefolder, 'converted')

  def unpack(self, filename : str, filepath : str) -> None:
    '''Unpacks an mmrs file into its temp directory'''
    if not os.path.isdir(self.convfolder):
      os.mkdir(self.convfolder)

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
        temp_addr = int(split[1], 16)

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

# META OUTPUT
class FlowStyleList(list):
  pass

class HexInt(int):
    pass

def represent_flow_style_list(dumper, data):
    return dumper.represent_sequence('tag:yaml.org,2002:seq', data, flow_style=True)

def represent_hexint(dumper, data):
    return dumper.represent_scalar('tag:yaml.org,2002:int', f"0x{data:X}")

yaml.add_representer(FlowStyleList, represent_flow_style_list)
yaml.add_representer(HexInt, represent_hexint)

def write_metadata(folder: str, base_name: str, cosmetic_name: str, meta_bank, song_type: str, categories, zsounds: dict[str, dict[str, int]] = None, formmask: list[str] = None):
  metadata_file_path = f"{folder}/{base_name}.metadata"
  
  yaml_dict : dict = {
    "game": "mm",
    "metadata": {
      "display name": cosmetic_name,
      "instrument set": HexInt(meta_bank) if isinstance(meta_bank, int) else meta_bank,
      "song type": song_type,
      "music groups": FlowStyleList([HexInt(cat) for cat in categories]),
    }
  }

  if zsounds:
    yaml_dict["metadata"]["audio samples"] = zsounds

  with open(metadata_file_path, "w", encoding="utf-8") as f:
    yaml.dump(yaml_dict, f, sort_keys=False, allow_unicode=True)
    
  if formmask:
    with open(metadata_file_path, 'a', encoding='utf-8') as f:
      f.write("formmask: [\n")
      
      for i, value in enumerate(formmask):
        comment = f"Channel {i}" if i < 16 else "Cumulative States"
        f.write(f'  "{value}"')
        
        if i != len(formmask) - 1:
          f.write(",")
          
        f.write(f" # {comment}\n")
        
      f.write("]\n")

def convert_standalone(file, base_folder, rel_path) -> None:
  '''Processes and converts a zseq into a new mmrs file'''
  cosmetic_name : str = None
  meta_bank     : int = None
  song_type     : str = None

  # filename = os.path.splitext(os.path.basename((remove_diacritics(file))))[0]
  filename = os.path.splitext(os.path.basename((file)))[0]
  filepath = os.path.abspath(file)

  # Create the temp folder and ensure it deletes itself if an exception occurs
  with tempfile.TemporaryDirectory(prefix='zseq_convert_') as tempfolder:
    standalone = StandaloneSequence(filename, base_folder, tempfolder)

    # Skip already converted files
    if os.path.isfile(f'{standalone.convfolder}/{filename}.zseq'):
      return

    # Copy the sequence file to the temp folder
    standalone.copy(filepath)

    cosmetic_name = re.sub(r'\s+', ' ', re.sub(r'(^|\W)(songforce|songtest)(?=\W|$)', '', standalone.filename, flags=re.IGNORECASE)).strip() or "???"
    meta_bank = int(standalone.instrument_set, 16)

    # 0x28 and higher indicate a custom instrument bank
    try:
      if meta_bank > 0x27:
        raise ValueError(f'ERROR: Error processing zseq file: {filename}.zseq! Instrument bank outside valid values!')
    except:
      raise ValueError(f'ERROR: Error processing zseq file: {filename}.zseq! Invalid instrument bank value!')

    # Check for mixed BGM and Fanfare categories
    ff_or_bgm = [category in FANFARE_CATEGORIES for category in standalone.categories]

    if all(ff_or_bgm):
      song_type = 'fanfare'
    elif not all(ff_or_bgm) and any(ff_or_bgm):
      raise ValueError(f'ERROR: Error processing zseq file: {filename}.zseq! Mixed BGM and Fanfare categories!')
    else:
      song_type = 'bgm'

    # Write the meta file
    write_metadata(tempfolder, standalone.filename, cosmetic_name, meta_bank, song_type, standalone.categories)

    standalone.pack(standalone.filename, rel_path)

def convert_archive(file, base_folder, rel_path) -> None:
  '''Processes and converts an old mmrs file into a new mmrs file'''
  cosmetic_name : str = ''
  meta_bank     : str = ''
  song_type     : str = ''
  categories          = []
  zsounds : dict[str, dict[str, int]] = {}

  #filename = os.path.splitext(os.path.basename((remove_diacritics(file))))[0]
  filename = os.path.splitext(os.path.basename((file)))[0]
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

    # The file is already converted, so move on
    if any(f.endswith('.metadata') for f in os.listdir(tempfolder)):
      return

    cosmetic_name = re.sub(r'\s+', ' ', re.sub(r'(^|\W)(songforce|songtest)(?=\W|$)', '', filename, flags=re.IGNORECASE)).strip() or "???"
    original_temp = tempfolder

    # Process the categories file
    with open(f'{tempfolder}/{archive.categories}', 'r') as text:
      categories = text.readline().strip()

      # There are two valid delimiters
      if '-' in categories:
        categories = [int(c, 16) for c in categories.split('-')]
      else:
        try:
          categories = [int(c, 16) for c in categories.split(',')]
        except:
          raise Exception(f'ERROR: Error processing categories file: {filename}.mmrs! Categories cannot be separated!')

      # Check for mixed BGM and Fanfare categories
      ff_or_bgm = [category in FANFARE_CATEGORIES for category in categories]

      if all(ff_or_bgm):
        song_type = 'fanfare'
      elif not all(ff_or_bgm) and any(ff_or_bgm):
        raise ValueError(f'ERROR: Error processing categories file: {filename}.mmrs! Mixed BGM and Fanfare categories!')
      else:
        song_type = 'bgm'

    # If there's multiple sequence files, loop through them
    for base_name, ext in archive.sequences:
      # Create a new temp folder for each individual sequence file
      with tempfile.TemporaryDirectory(prefix='mmrs_convert_2_') as song_folder:
        formmask: list[str] = []

        meta_bank = int(base_name, 16) # The instrument set is the name of the sequence

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

          meta_bank = 'custom' # The file uses a custom instrument set

          for item in os.listdir(original_temp):
            if item.endswith('.zsound'):
              shutil.copy2(os.path.join(original_temp, item), song_folder)

          for key, value in archive.zsounds.items():
            if key and value:
              zsounds[f"{key}.zsound"] = { "temp address": value }

        # Copy the formmask file into the temp folder
        if base_name in archive.formmasks:
          formmask_path = os.path.join(original_temp, archive.formmasks[base_name])
          try:
            with open(formmask_path, 'r', encoding='utf-8') as f:
              formmask = yaml.safe_load(f)
          except Exception as e:
            raise Exception(f"ERROR: Failed to parse formmask file {formmask_path}: {str(e)}")

        # Copy extra non-processed files
        for item in os.listdir(original_temp):
          if item.endswith(('.seq', '.zseq', '.aseq', '.zbank', '.bankmeta', '.zsound', '.formmask')) or item == 'categories.txt':
            continue

          full_item_path = os.path.join(original_temp, item)
          if os.path.isfile(full_item_path):
            shutil.copy2(full_item_path, song_folder)

        # Write the meta file
        write_metadata(song_folder, base_name, cosmetic_name, meta_bank, song_type, categories, zsounds if zsounds else None, formmask if formmask else None)

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
      spinner_thread.join()

      print(f"{RED}Error processing {full_path}:{RESET}")
      print(f"{YELLOW}{str(e)}{RESET}")
      logging.error(f"Error processing {full_path}", exc_info=True)

      spinner_thread = start_spinner("Processing files...")

  # Let the user know the process is ongoing
  spinner_thread = start_spinner("Processing files...")

  try:
    for file in FILES:
      # If the path is a directory, get all files and then process them copying directories
      if os.path.isdir(file):
        # DEBUG: Print out which directory is being processed
        # print(f"{CYAN}Processing directory:{RESET} {file}")
        base_folder = os.path.abspath(file)
        file_list = get_files_from_directory(base_folder)

        for full_path, rel_path in file_list:
          # DEBUG: Print out which file in the subdir is being processed
          # print(f"{GRAY_248}  └─ {rel_path}{RESET}")
          process_file(full_path, base_folder, rel_path)

      # If the path is a file, process the file directly
      else:
        # DEBUG: Print out the which file is being processed
        # print(f"{CYAN}Processing file:{RESET} {file}")
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
