# ImportTagsToJson

ImportTagsToJson is a Python tool that maps field names from `MyTags.txt` onto JSON files exported from CfgBin Editor.
It supports multiple games in the Yo-kai Watch series and other games with compatible tag definitions. 
Users can choose which field to use as the key for each entry or store entries in arrays instead.

## Features

- Import field definitions from `MyTags.txt`
- Support multiple game-specific tag schemas
- Map entries using a user-selected field
- Store entries as dictionaries or arrays
- Configure input and output directories
- Save user preferences between sessions

## Games

This program supports the following games:
- Yo-kai Watch 1 (YW1)
- Yo-kai Watch 2 (YW2)
- Yo-kai Watch 3 (YW3)
- Yo-kai Watch 4 (YW4)
- Yo-kai Watch Blasters (YWB)                
- Yo-kai Watch Blasters 2 (YWB2)
- Y School Heroes (YSH)
- Ni no Kuni: Wrath of the White Witch (NNK1)
- Summoners War (SW)
- Inazuma Eleven GO (IEGO)

## Config

This program uses `settings.json` file to store your preferred settings.
Inside settings it stores:
- Directory where your raw JSON files are stored
- Output directory
- Currently selected game title

## Requirements

- **`MyTags.txt`**: A compatible tag definition file. Place it in the same directory as `ImportTagsToJson.py` or `ImportTagsToJson.exe`.
- **Input JSON files**: JSON files exported from CfgBin Editor using the expected `cfg.bin` export structure. Place them in the `json` folder or configure the input directory through the program.
- **Output directory**: Directory where the program can save the generated JSON files. You can configure this directory through the program's menu or inside `settings.json` file.

The Python source version requires a compatible Python installation. The standalone Windows executable does not require Python to be installed separately.

# Installation

ImportTagsToJson can be installed 2 ways:

1. Python source version

This version requires you to have Python 3.10 (or newer) installed on your device.
You can automatically start the python script through `Start.bat` file.

2. Standalone Windows executable

This version doesn't require you to have Python installed on your device (but still needs external files such as `MyTags.txt` and the input JSON files).
If you need to edit the original script, you will need to download Python source code, 
then build the program with PyInstaller if you want to rebuild the executable file.
Starts the program with `ImportTagsToJson.exe` file.

# Usage

During iteration, you can choose which field to use as the dictionary key or if they should be stored as arrays.

How to import from `MyTags.txt` to exported JSON file:
- Place your raw JSON file inside `./json` folder or configure path to the JSON folder
- Open the program and select first option
- Write name of your JSON file (together with `.json` e.g.: `example.json`).
- If you want to map the entries by value, simply write its name, otherwise just press enter to skip this option (values will be stored inside array)
- The program will create new JSON file inside output directory (path to file will be displayed at the end)

Example usage:
```
====================--COMMAND LIST--====================
1 - Import tags from MyTags.txt to JSON file
2 - Set game title (Current: YW2)
3 - Set output directory (Current: C:\Example\Path\To\Program)
4 - Set JSON directory (Current: C:\Example\Path\To\Program\json)
========================================================
Input: 1
JSON File name: battle_states_effect_0.02k.json
{'SteffCat': 1, 'SteffID': '0x105566FE', 'Unk-AlwaysZero': 0, 'Duration': 0, 'IsContinuous': 0}
Map BTLSTEFF_INFO schema by value?
(Write value name or press enter to use array instead)
SteffID

Saved: C:\Example\Path\To\Program\battle_states_effect_0.02k.json
```

# Links

1. CfgBin Editor fork: https://github.com/onepiecefreak3/CfgBinEditor

2. PyInstaller: https://pyinstaller.org/en/stable/installation.html

3. MyTags GitHub Repository: https://github.com/light8227/yw-stuff/tree/master

# Credits

Thanks to YW Modding Zone for providing `MyTags.txt` file