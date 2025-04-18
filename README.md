# Majora's Mask Music File Updater
This is a python script that copies and updates standalone sequence files (`.zseq`) and packed music files (`.mmrs`) to the updated packed format that uses a META (`.meta`) file to store metadata.

## 🔧 How To Use
To use this script, follow the steps below:

> 1. Select a folder or file(s) within a folder
> 2. Drag the folder or file(s) onto the script file (`MMR Music Updater.py`)
> 3. A terminal window will open and display the current file(s) being processed
> 4. After processing, the terminal window will wait for user input before closing

That's it — your files are now copied and converted!

## 📂 Output Folder Location
Converted files are placed in an output folder named `converted`, which is located in the following location depending on the input type:

#### 📁 Folder:
`../path/to/input_folder/converted/`

> [!IMPORTANT]
> When using a folder for input, the directoy structure will be preserved. All supported files are converted and placed in their corresponding locations within the `converted` folder.
>
> So don't worry — you can safely convert an organized folder without losing its original structure!

#### 📄 File(s):
`../path/to/file_location/converted/`
