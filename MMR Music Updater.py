# Set to True to use spinner, false to show full file logs
USE_SPINNER = True

# Begin script
import os, sys, time
import re
import tempfile
import shutil
import zipfile
import yaml
import unicodedata
from collections import defaultdict
from typing import Final

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

# HANDLE THREADING
import threading, itertools
from concurrent.futures import ThreadPoolExecutor

done_flag = threading.Event()
spinner_thread = threading.Thread()

def spinner_task(message: str, done_flag: threading.Event) -> None:
    for frame in itertools.cycle(SPINNER_FRAMES):
        if done_flag.is_set():
            break
        sys.stderr.write(f"{PL}{CL}{PINK_204}{frame}{RESET} {GRAY_245}{message}{RESET}\n")
        sys.stderr.flush()
        time.sleep(0.07)
    if USE_SPINNER:
      sys.stderr.write(f"{PL}{CL}{GREEN_79}✓{RESET} {GRAY_245}{message}{RESET}\n")
    else:
      sys.stderr.write(f"{GREEN_79}✓{RESET} {GRAY_245}{message}{RESET}\n")
    sys.stderr.flush()

def start_spinner(message: str):
    if not USE_SPINNER:
        print(f"{GRAY_245}{message}{RESET}")

        class DummyThread:
          def join(self): pass
        return DummyThread()

    done_flag.clear()
    thread = threading.Thread(target=spinner_task, args=(message, done_flag))
    thread.start()
    return thread

# HANDLE ERROR LOGGING
import logging
logger = logging.getLogger('mmr_music_updater')
logger.setLevel(logging.ERROR)
logger.propagate = False
_log_handler = None

def log_error(message: str, exc_info = True):
  global _log_handler
  if _log_handler is None:
    _log_handler = logging.FileHandler('mmr-music-updater_errors.log', mode='a', encoding='utf-8')
    _log_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    logger.addHandler(_log_handler)

  logger.error(message, exc_info=exc_info)

def remove_diacritics(text: str) -> str:
  '''Normalizes filenames to prevent errors caused by diacritics'''
  normalized = unicodedata.normalize('NFD', text)
  without_diacritics = ''.join(c for c in normalized if unicodedata.category(c) != 'Mn')

  return without_diacritics

# HANDLE MUSIC FILE CLASSES
class SkipFileException(Exception):
  pass

class StandaloneSequence:
  def __init__(self, filename, tempfolder) -> None:
    self.filename, self.instrument_set, self.categories = self.parse_zseq_filename(filename)
    self.tempfolder = tempfolder

  def parse_zseq_filename(self, filename) -> tuple[str, int, list[str]]:
    parts = os.path.splitext(filename)[0].split('_')

    if len(parts) != 3:
      raise Exception(f"StandaloneSequence Error: Invalid filename format.")

    return parts[0], int(parts[1], 16), parts[2].split('-')

  def copy(self, filepath) -> None:
    temp_seq_filepath = os.path.join(self.tempfolder, f"{self.filename}.seq")

    shutil.copyfile(filepath, temp_seq_filepath)

class MusicArchive:
  def __init__(self, tempfolder):
    self.sequences: list[tuple[str, str]] = []
    self.categories: str = None
    self.banks: dict[str, tuple[str, str]] = {}
    self.formmasks: dict[str, str] = {}
    self.zsounds : dict[str, int] = {}
    self.tempfolder = tempfolder

  def unpack(self, filepath: str) -> None:
    if os.path.exists(self.tempfolder):
      os.rmdir(self.tempfolder)

    with zipfile.ZipFile(filepath, 'r') as zip_archive:
      for f in zip_archive.namelist():
        if f.endswith(".metadata"):
          raise SkipFileException("Archive contains .metadata, skipping.")
      zip_archive.extractall(self.tempfolder)

    sample_counter: int = 1
    for f in os.listdir(self.tempfolder):
      filename = os.path.basename(f)
      base_name = os.path.splitext(f)[0]
      extension = os.path.splitext(f)[1].lower()

      if extension in SEQ_EXTS:
        self.sequences.append((base_name, extension))
        continue

      if extension == ".zbank":
        bankmeta_path = f'{base_name}.bankmeta'
        if not os.path.exists(os.path.join(self.tempfolder, bankmeta_path)):
          raise FileNotFoundError(f"Missing bankmeta for {filepath}!")
        self.banks[base_name] = (filename, bankmeta_path)
        continue

      if extension == ".formmask":
        self.formmasks[base_name] = filename
        continue

      if extension == ".zsound":
        self.process_zsounds(filename, sample_counter)

      if f == "categories.txt":
        self.categories = f

    if not self.sequences:
      raise FileNotFoundError(f'MusicArchive Error: No sequence file found!')
    if not self.categories:
      raise FileNotFoundError(f'MusicArchive Error: No categories.txt file found!')

  def process_zsounds(self, file: str, sample_counter: int):
    base_name: str = file.split(".zsound")[0]
    parts: tuple = base_name.split("_")

    sample_name: str = ""
    temp_address: int = -1

    try:
      if len(parts) == 2:
        sample_name = parts[0]
        temp_address = int(parts[1], 16)

      elif len(parts) == 1:
        sample_name = f"Sample{sample_counter}"
        temp_address = int(parts[0], 16)
        sample_counter += 1

      else:
        raise ValueError(f"process_zsounds Error: An exception occured while processing a zsound file: {file} - wrong format!")
    except ValueError as e:
      raise ValueError(f"process_zsounds Error: {e}")

    old_path = os.path.join(self.tempfolder, file)
    new_path = os.path.join(self.tempfolder, f"{sample_name}.zsound")

    suffix: int = 1
    while os.path.exists(new_path):
      new_path = os.path.join(self.tempfolder, f"{sample_name}{suffix}.zsound")
      suffix += 1

    try:
      shutil.move(old_path, new_path)
    except:
      return

    self.zsounds[os.path.splitext(os.path.basename(new_path))[0]] = HexInt(temp_address)

# Write Metadata File
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

def write_metadata(folder: str, base_name: str, cosmetic_name: str, instrument_set, song_type: str, categories, zsounds: dict[str, dict[str, int]] = None, formmask: list[str] = None):
  metadata_file_path = f"{folder}/{base_name}.metadata"

  yaml_dict : dict = {
    "game": "mm",
    "metadata": {
      "display name": cosmetic_name,
      "instrument set": HexInt(instrument_set) if isinstance(instrument_set, int) else instrument_set,
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

def clean_cosmetic_name(filename: str) -> str:
  return re.sub(r'\s+', ' ', re.sub(r'(^|\W)(songforce|songtest)(?=\W|$)', '', filename, flags=re.IGNORECASE)).strip() or "???"

def parse_categories(raw_categories: list[str]) -> list[int]:
  return [int(c.strip(), 16) for c in raw_categories]

def get_song_type(categories, filename: str) -> str:
  ff_or_bgm = [category in FANFARE_CATEGORIES for category in categories]

  if all(ff_or_bgm):
    return 'fanfare'
  elif not all(ff_or_bgm) and any(ff_or_bgm):
    raise ValueError(f"ERROR: Mixed BGM and Fanfare categories in {filename}!")
  else:
    return 'bgm'

def parse_categories_and_song_type(category_filepath: str, filename: str) -> tuple[list[int], str]:
  with open(category_filepath, 'r') as f:
    raw_categories = f.readline().strip()

  if '-' in raw_categories:
    parts = raw_categories.split('-')
  else:
    parts = raw_categories.split(',')

  try:
    categories = [int(p.strip(), 16) for p in parts if p.strip()]
  except Exception as e:
    raise Exception(f'ERROR: Error processing categories file: {filename}.mmrs! Categories cannot be separated!')

  song_type = get_song_type(categories, filename)

  return categories, song_type

def copy_unprocessed_files(source_dir: str, destination_dir: str) -> None:
  skip_extensions: list[str] = ['.seq', '.zseq', '.aseq', '.zbank', '.bankmeta', '.zsound', '.formmask']
  skip_categories: str = 'categories.txt'

  for file in os.listdir(source_dir):
    name: str = os.path.basename(file)
    extension: str = os.path.splitext(file)[1]

    if extension.lower() in skip_extensions or name.lower() == skip_categories:
      continue

    shutil.copyfile(os.path.join(source_dir, file), os.path.join(destination_dir, file))

def pack(filename: str, tempfolder: str, destination_dir: str) -> None:
    '''Packs the temp folder into a new mmrs file'''
    archive_base = os.path.join(destination_dir, filename)
    zip_path = f"{archive_base}.zip"
    mmrs_path = f"{archive_base}.mmrs"

    shutil.make_archive(archive_base, 'zip', tempfolder)

    if os.path.exists(mmrs_path):
      os.remove(mmrs_path)

    os.rename(zip_path, mmrs_path)

# Convert zseq files
def convert_standalone(input_file: str, destination_dir: str) -> None:
  filename = os.path.splitext(os.path.basename(input_file))[0]
  filepath = os.path.abspath(input_file)

  # If the file already exists, return
  if os.path.isfile(f"{destination_dir}/{filename}.mmrs"):
    return

  # Begin conversion
  with tempfile.TemporaryDirectory(prefix='zseq_convert_') as tempfolder:
    standalone_seq = StandaloneSequence(filename, tempfolder)

    try:
      standalone_seq.copy(filepath)

      cosmetic_name = clean_cosmetic_name(standalone_seq.filename)
      instrument_set = standalone_seq.instrument_set

      # 0x28 and higher indicate a custom instrument bank
      try:
        if instrument_set > 0x27:
          raise ValueError(f'ERROR: Error processing zseq file: {filename}.zseq! Instrument bank outside valid values!')
      except Exception as e:
        raise Exception(e)

      categories = parse_categories(standalone_seq.categories)
      song_type = get_song_type(categories, filename)

      # Write the metadata and pack the file
      write_metadata(standalone_seq.tempfolder, standalone_seq.filename, cosmetic_name, instrument_set, song_type, categories)
      pack(standalone_seq.filename, standalone_seq.tempfolder, destination_dir)

    except Exception as e:
      raise Exception(e)

# Handling for multiple sequences in an archive
def process_archive_sequences(archive: MusicArchive, destination_dir: str, filename: str, cosmetic_name: str, categories: list, song_type: str, original_temp: str):
  zsounds: dict[str, int] = {}
  formmask = None

  for base_name, ext in archive.sequences:
    with tempfile.TemporaryDirectory(prefix='mmrs_convert_2_') as song_folder:
      instrument_set = int(base_name, 16)

      original_sequence = os.path.join(original_temp, f'{base_name}{ext}')
      new_sequence_path = os.path.join(song_folder, f'{base_name}.seq')
      shutil.copyfile(original_sequence, new_sequence_path)

      if base_name in archive.banks:
        bank, bankmeta = archive.banks[base_name]

        shutil.copyfile(os.path.join(original_temp, bank), os.path.join(song_folder, bank))
        shutil.copyfile(os.path.join(original_temp, bankmeta), os.path.join(song_folder, bankmeta))

        instrument_set = 'custom'

        for item in os.listdir(original_temp):
          if item.endswith(".zsound"):
            shutil.copyfile(os.path.join(original_temp, item), os.path.join(song_folder, item))

        for key, value in archive.zsounds.items():
          if key and value:
              zsounds[f"{key}.zsound"] = { "temp address": value }

      if base_name in archive.formmasks:
        formmask_path = os.path.join(original_temp, archive.formmasks[base_name])
        try:
          with open(formmask_path, 'r', encoding='utf-8') as f:
            formmask = yaml.safe_load(f)
        except Exception as e:
          raise Exception(e)

      copy_unprocessed_files(original_temp, song_folder)

      write_metadata(song_folder, base_name, cosmetic_name, instrument_set, song_type, categories, zsounds if zsounds else None, formmask if formmask else None)

      if len(archive.sequences) > 1:
        pack(f'{filename}_{base_name}', song_folder, destination_dir)
      else:
        pack(f'{filename}', song_folder, destination_dir)

# Convert mmrs files
def convert_archive(input_file: str, destination_dir: str):
  filename = os.path.splitext(os.path.basename(input_file))[0]
  filepath = os.path.abspath(input_file)

  with tempfile.TemporaryDirectory(prefix='mmrs_convert_') as tempfolder:
    archive = MusicArchive(tempfolder)
    original_temp = archive.tempfolder

    try:
      archive.unpack(filepath)

      cosmetic_name: str = clean_cosmetic_name(filename)

      categories_path: str = os.path.join(original_temp, archive.categories)
      categories, song_type = parse_categories_and_song_type(categories_path, filename)

      process_archive_sequences(archive, destination_dir, filename, cosmetic_name, categories, song_type, original_temp)

    except SkipFileException:
      return
    except Exception as e:
      raise Exception(e)

# Process single file
def processing_file(input_file: str, base_folder: str, conversion_folder: str) -> None:
  try:
    extension = os.path.splitext(input_file)[1]
    relative_path = os.path.relpath(input_file, base_folder)
    destination_dir = os.path.dirname(os.path.join(conversion_folder, relative_path))

    # Create the destination and copy the file to the destination
    os.makedirs(destination_dir, exist_ok=True)

    if extension == ".zseq":
      convert_standalone(input_file, destination_dir)

    elif extension == ".mmrs":
      convert_archive(input_file, destination_dir)

  except Exception as e:
    raise Exception(f"processing_file Error: {e}")

# Begin processing files
def process_with_spinner(input_file: str, base_folder: str, conversion_folder: str, show_file_log: bool = False) -> None:
  global spinner_thread
  try:
    processing_file(input_file, base_folder, conversion_folder)
  except Exception as e:
    done_flag.set()
    spinner_thread.join()
    print(f"{RED}Error processing {input_file}:{RESET}")
    print(f"{YELLOW}{str(e)}{RESET}")
    log_error(f"Error processing {input_file}", exc_info=True)
    spinner_thread = start_spinner("Processing file...")

def process_files(base_folder: str, conversion_folder: str, files: list[str], show_file_log: bool = False):
  os.makedirs(conversion_folder, exist_ok=True)

  files_by_dir = defaultdict(list)
  for input_file in files:
    rel_path = os.path.relpath(input_file, base_folder)
    dir_path = os.path.dirname(rel_path)
    files_by_dir[dir_path].append((input_file, os.path.basename(rel_path)))

  with ThreadPoolExecutor() as executor:
    for dir_path, file_entries in sorted(files_by_dir.items()):
      if not USE_SPINNER and show_file_log:
        print(f"{CYAN}Processing Directory:{RESET} {os.path.join(os.path.basename(base_folder), dir_path)}")
        for _, filename in sorted(file_entries, key=lambda x: x[1]):
          print(f"{GRAY_248}  └─ Processing file:{RESET} {filename}")

      for input_file, _, in file_entries:
        executor.submit(process_with_spinner, input_file, base_folder, conversion_folder, show_file_log)

def convert_music_files() -> None:
  global spinner_thread

  spinner_thread = start_spinner("Processing files...")

  try:
    for file in FILES:
      filepath = os.path.abspath(file)

      if os.path.isdir(file):
        base_folder = filepath
        parent_folder = os.path.dirname(base_folder)
        conversion_folder: str = os.path.join(parent_folder, f'{os.path.basename(base_folder)}_converted')

        files_to_process = [
          os.path.join(root, name)
          for root, _, files in os.walk(base_folder)
          for name in files
        ]

        if not USE_SPINNER:
          print(f"{CYAN}Processing directory:{RESET} {os.path.basename(base_folder)}")

        process_files(base_folder, conversion_folder, files_to_process, True)

      elif os.path.isfile(file):
        base_folder = os.path.dirname(filepath)
        conversion_folder: str = os.path.join(base_folder, 'converted_files')

        if not USE_SPINNER:
          print(f"{CYAN}Processing File:{RESET} {os.path.basename(file)}")

        process_files(base_folder, conversion_folder, [file])

  finally:
    done_flag.set()
    spinner_thread.join()
    if USE_SPINNER:
      sys.stdout.write(f"{PL}{CL}{GREEN_79}✓{RESET} {GRAY_245}All files processed.{RESET}\n")
    else:
      sys.stderr.write(f"{GREEN_79}✓{RESET} {GRAY_245}All files processed.{RESET}\n")
    sys.stdout.flush()

if __name__ == '__main__':
  convert_music_files()
  os.system('pause')
