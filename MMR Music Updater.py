import os, sys, time
import shutil
import zipfile
import unicodedata
import threading, itertools

from typing import Final

FILES = sys.argv[1:]

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

FANFARE_CATEGORIES : Final[list[str]] = [
  # GROUPS
  '8', '9', '10',
  # INDIVIDUAL
  '108', '109', '119', '120', '121', '122',
  '124', '137', '139', '13D', '13F', '141',
  '152', '155', '177', '178', '179', '17C',
  '17E',
]

def spinner_task(message: str, done_flag: threading.Event):
  for frame in itertools.cycle(SPINNER_FRAMES):
    if done_flag.is_set():
      break
    sys.stdout.write(f"{PL}{CL}{PINK_204}{frame}{RESET} {GRAY_245}{message}{RESET}\n")
    sys.stdout.flush()
    time.sleep(0.07)
  sys.stdout.write(f"{PL}{CL}{GREEN_79}✓{RESET} {GRAY_245}{message}{RESET}\n")
  sys.stdout.flush()

def remove_diacritics(text: str):
  normalized = unicodedata.normalize('NFD', text)
  without_diacritics = ''.join(c for c in normalized if unicodedata.category(c) != 'Mn')

  return without_diacritics

def parse_hex_id(value: str) -> int:
    value = value.lower().strip()
    return int(value, 16) if value.startswith("0x") else int(value, 16)

class StandaloneSequence:
  def __init__(self, filename, base_folder):
    self.basefolder : str = base_folder
    self.tempfolder : str = os.path.join(self.basefolder, 'temp')
    self.convfolder : str = os.path.join(self.basefolder, 'converted')

    self.filename = None
    self.instrument_set = None
    self.categories = []

    self._parse_filename(filename)

  def _parse_filename(self, filename):
    basename = os.path.basename(filename)
    name_no_ext = basename.replace('.zseq', '')

    parts = name_no_ext.split('_')

    if len(parts) != 3:
      raise ValueError()

    self.filename = remove_diacritics(parts[0])
    self.instrument_set = parts[1]
    self.categories = parts[2].split('-')

  def copy(self, filepath):
    if not os.path.isdir(self.convfolder):
      os.mkdir(self.convfolder)

    if os.path.isdir(self.tempfolder):
      shutil.rmtree(self.tempfolder)

    if os.path.isdir(self.filename + '.zip'):
      os.remove(self.filename + '.zip')

    if os.path.isdir(self.filename + '.mmrs'):
      os.remove(self.filename + '.mmrs')

    os.mkdir(self.tempfolder)

    with open(filepath, 'rb') as src:
      with open(f'{self.tempfolder}/{self.filename}.seq', 'wb') as dst:
        dst.write(src.read())

  def pack(self, filename, rel_path):
    output_path = os.path.join(self.convfolder, os.path.dirname(rel_path))
    os.makedirs(output_path, exist_ok=True)

    archive_path = os.path.join(output_path, filename)
    shutil.make_archive(archive_path, 'zip', self.tempfolder)
    os.rename(f'{archive_path}.zip', f'{archive_path}.mmrs')

    if os.path.isdir(self.tempfolder):
      shutil.rmtree(self.tempfolder)

class MusicArchive:
  def __init__(self, base_folder):
    self.sequences  : list[tuple[str, str]] = [] # (name, extension)
    self.categories : str = None
    self.banks      : dict[str, tuple[str, str]] = {} # { '28': ('28.zbank', '28.bankmeta')}
    self.formmasks  : dict[str, str] = {} # { '28': '28.formmask' }

    # Store zsounds in a dictionary
    self.zsounds : dict[str, str] = {}

    # Get the paths
    self.basefolder : str = base_folder
    self.tempfolder : str = os.path.join(self.basefolder, 'temp')
    self.convfolder : str = os.path.join(self.basefolder, 'converted')

  def unpack(self, filename : str, filepath : str) -> None:

    if not os.path.isdir(self.convfolder):
      os.mkdir(self.convfolder)

    if os.path.isdir(self.tempfolder):
      shutil.rmtree(self.tempfolder)

    if os.path.isdir(filename + '.zip'):
      os.remove(filename + '.zip')

    if os.path.isdir(filename + '.mmrs'):
      os.remove(filename + '.mmrs')

    with zipfile.ZipFile(filepath, 'r') as zip_archive:
      zip_archive.extractall(self.tempfolder)

    for f in os.listdir(self.tempfolder):
      if f.endswith(SEQ_EXTS):
        base, ext = os.path.splitext(f)
        self.sequences.append((base, ext))
        continue

      if f.endswith('.zbank'):
        base = os.path.splitext(f)[0]
        zbank_path = f
        bankmeta_path = f'{base}.bankmeta'

        if os.path.exists(os.path.join(self.tempfolder, bankmeta_path)):
          self.banks[base] = (zbank_path, bankmeta_path)
        else:
          raise FileNotFoundError(f'Missing bankmeta for {zbank_path}!')
        continue

      if f.endswith('.bankmeta'):
        continue

      if f == 'categories.txt':
        self.categories = f
        continue

      if f.endswith('.formmask'):
        base = os.path.splitext(f)[0]
        self.formmasks[base] = f
        continue

      if f.endswith('.zsound'):
        split = f.split('.zsound')
        base = split[0]
        split = base.split('_')

        if len(split) != 2:
          raise Exception(f'ERROR: An exception occured while processing a zsound file: {f}! Too many or too little parameters present in filename!')

        name = split[0]
        temp_addr = split[1]

        os.rename(f'{self.tempfolder}/{f}', f'{self.tempfolder}/{name}.zsound')

        self.zsounds[name] = temp_addr
        continue

    if not self.sequences:
      raise FileNotFoundError('No sequence file!')
    if not self.categories:
      raise FileNotFoundError('No categories file!')

  def pack(self, filename, rel_path) -> None:
    output_path = os.path.join(self.convfolder, os.path.dirname(rel_path))
    os.makedirs(output_path, exist_ok=True)

    archive_path = os.path.join(output_path, filename)
    shutil.make_archive(archive_path, 'zip', self.tempfolder)
    os.rename(f'{archive_path}.zip', f'{archive_path}.mmrs')

    if os.path.isdir(self.tempfolder):
      shutil.rmtree(self.tempfolder)

def get_files_from_directory(directory: str) -> list[tuple[str, str]]:
  files = []
  for root, _, filenames in os.walk(directory):
    for filename in filenames:
      full_path = os.path.join(root, filename)
      rel_path = os.path.relpath(full_path, start=directory)
      files.append((full_path, rel_path))

  return files

def convert_standalone(file, base_folder, rel_path) -> None:
  cosmetic_name : str = ''
  meta_bank     : str = ''
  song_type     : str = ''
  categories    : str = ''

  filename = os.path.splitext(os.path.basename((remove_diacritics(file))))[0]
  filepath = os.path.abspath(file)

  standalone = StandaloneSequence(filename, base_folder)

  standalone.copy(filepath)

  cosmetic_name = standalone.filename.replace('songforce', '').replace('songtest', '').strip(" _-")
  meta_bank = standalone.instrument_set

  ff_or_bgm = [category.upper() in FANFARE_CATEGORIES for category in standalone.categories]

  if all(ff_or_bgm):
    song_type = 'fanfare'
  elif any(boolean == False for boolean in ff_or_bgm) and any(boolean == True for boolean in ff_or_bgm):
    raise Exception(f'ERROR: Mixed categories for categories in .zseq file: {filename}.zseq!')
  else:
    song_type = 'bgm'

  categories = ','.join(standalone.categories)

  with open(f'{standalone.tempfolder}/{standalone.filename}.meta', 'a') as meta:
    meta.write(cosmetic_name)
    meta.write('\n' + meta_bank)
    meta.write('\n' + song_type)
    meta.write('\n' + categories)

  standalone.pack(standalone.filename, rel_path)

def convert_archive(file, base_folder, rel_path) -> None:
  cosmetic_name : str = ''
  meta_bank     : str = ''
  song_type     : str = ''
  categories          = ''
  zsounds : list[str] = []

  filename = os.path.splitext(os.path.basename((remove_diacritics(file))))[0]
  filepath = os.path.abspath(file)

  archive = MusicArchive(base_folder)

  if os.path.isfile(f'{archive.convfolder}/{filename}.mmrs'):
    return

  try:
    archive.unpack(filename, filepath)
  except:
    return

  cosmetic_name = filename.replace('songforce', '').replace('songtest', '').strip(" _-")
  original_temp = archive.tempfolder

  with open(f'{archive.tempfolder}/{archive.categories}', 'r') as text:
    categories = ''.join(text.readlines(0))

    if '-' in categories:
      categories = categories.split('-')
    else:
      categories = categories.split(',')

    ff_or_bgm = [category.upper() in FANFARE_CATEGORIES for category in categories]

    if all(ff_or_bgm):
      song_type = 'fanfare'
    elif any(boolean == False for boolean in ff_or_bgm) and any(boolean == True for boolean in ff_or_bgm):
      raise Exception(f'ERROR: Mixed categories for categories.txt in .mmrs file: {filename}.mmrs!')
    else:
      song_type = 'bgm'

    categories = ','.join(categories)

  for base_name, ext in archive.sequences:
    song_folder = f'{original_temp}_{base_name}'
    os.makedirs(song_folder, exist_ok=True)

    meta_bank = base_name

    # Copy sequence files
    original_seq = os.path.join(original_temp, f'{base_name}{ext}')
    new_seq_path = os.path.join(song_folder, f'{base_name}.seq')
    shutil.copy2(original_seq, new_seq_path)

    if base_name in archive.banks:
      zbank, bankmeta = archive.banks[base_name]
      shutil.copy2(os.path.join(original_temp, zbank), song_folder)
      shutil.copy2(os.path.join(original_temp, bankmeta), song_folder)

      meta_bank = '-'

      for item in os.listdir(original_temp):
        if item.endswith('.zsound'):
          shutil.copy2(os.path.join(original_temp, item), song_folder)

      for key, value in archive.zsounds.items():
        command = f'ZSOUND:{key}.zsound:{value}'
        zsounds.append(command)

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

    with open(os.path.join(song_folder, f'{base_name}.meta'), 'a') as meta:
      meta.write(cosmetic_name)
      meta.write('\n' + meta_bank)
      meta.write('\n' + song_type)
      meta.write('\n' + categories)
      if zsounds:
        for garbage in zsounds:
          meta.write('\n' + garbage)

    temp_archive = MusicArchive(base_folder)
    temp_archive.tempfolder = song_folder
    temp_archive.pack(f'{filename}_{base_name}', rel_path)

    if os.path.isdir(song_folder):
      shutil.rmtree(song_folder)

  if os.path.isdir(original_temp):
    shutil.rmtree(original_temp)

if __name__ == '__main__':
  def process_file(full_path, base_folder, rel_path):
    try:
      if full_path.endswith('.zseq'):
        convert_standalone(full_path, base_folder, rel_path)
      elif full_path.endswith('.mmrs'):
        convert_archive(full_path, base_folder, rel_path)
    except Exception as e:
      print(f"{RED}Error processing {full_path}: {e}{RESET}")

  # Spinner setup
  done_flag = threading.Event()
  spinner_thread = threading.Thread(target=spinner_task, args=("Processing files...", done_flag))
  spinner_thread.start()

  try:
    for file in FILES:
      if os.path.isdir(file):
        base_folder = os.path.abspath(file)
        file_list = get_files_from_directory(base_folder)

        for full_path, rel_path in file_list:
          process_file(full_path, base_folder, rel_path)

      else:
        base_folder = os.path.dirname(os.path.abspath(file))
        rel_path = os.path.basename(file)
        full_path = os.path.abspath(file)

        process_file(full_path, base_folder, rel_path)

  finally:
    done_flag.set()
    spinner_thread.join()

    sys.stdout.write(f"{PL}{CL}{GREEN_79}✓{RESET} {GRAY_245}All files processed.{RESET}\n")
    sys.stdout.flush()

  os.system('pause')
