# Majora's Mask Randomzier Music File Updater
This is a python script that copies and updates standalone sequence files (`.zseq`) and packed music files (`.mmrs`) to the updated packed format that uses a YAML metadata (`.metadata`) file to store metadata.

> [!NOTE]
> Music conversion is built into Majora's Mask Randomizer, so any old files detected will automatically be converted before writing music. This script acts as a standalone Python version of `MusicConversionUtils.cs` that users may use whenever they want to without needing to create a seed.

## 📋 Requirements
This script requires the PyYAML module:
```
pip install pyyaml
```

## 🔧 How To Use
To use this script, follow the steps below:

> 1. Select a folder or file(s) within a folder
> 2. Drag the folder or file(s) onto the script file (`MMR Music Updater.py`)
> 3. A terminal window will open and display the current file(s) being processed
> 4. After processing, the terminal window will wait for user input before closing

That's it — your files are now copied and converted!

> [!TIP]
> If you would rather see exactly which directories and files are being processed, you can change the `USE_SPINNER` value at the top of the script:
> - `True` — Prints just the spinner to the terminal
> - `False` — Prints every directory and file being processed to the terminal

## 📂 Output Folder Location
Converted files are placed in an output folder named `converted`, which is located in the following location depending on the input type:

#### 📁 Folder:
`../path/to/parent_folder/input_folder_converted/`

> [!IMPORTANT]
> When using a folder for input, the directory structure will be preserved. All supported files are converted and placed in their corresponding locations within the `input_folder_converted` folder.
>
> So don't worry — you can safely convert an organized folder without losing its original structure!

#### 📄 File(s):
`../path/to/file_location/converted/`
