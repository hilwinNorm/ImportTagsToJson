import json
import re
from pathlib import Path
import sys

# ============================================================
# Yokai Watch database mapper
#
# Put this .py file, MyTags.txt and the JSON files in the same
# directory, or change default DATA_DIR below.
# ============================================================

if getattr(sys, "frozen", False):
    # Running as a PyInstaller executable
    DATA_DIR = Path(sys.executable).resolve().parent
else:
    # Running as a regular Python script
    DATA_DIR = Path(__file__).resolve().parent

MYTAGS_PATH = DATA_DIR / "MyTags.txt"
    
SETTINGS_DIR = DATA_DIR / "settings.json"

CONFIG = {
    "GAME_MARKER": "YW2",
    "JSON_DIR": DATA_DIR / Path("json/"),
    "OUTPUT_PATH": DATA_DIR
    
}

MARKER_LIST=["YW1","YW2","YW3","YWB","YWB2","YW4", "YSH", "NNK1", "SW", "IEGO"]
NEXT_MARKER = {MARKER_LIST[i]: (i+1)%len(MARKER_LIST) for i in range(len(MARKER_LIST))}

def int_input(value):
    value = value.strip()
    if value.isdigit(): return int(value)
    return 0

def save_setting(setting_key, value):
    try:
        with open(SETTINGS_DIR, "r", encoding="utf-8") as f:
            settings = json.load(f)
    except FileNotFoundError:
        settings = {}
    settings[setting_key] = value
    with open(SETTINGS_DIR, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=4, ensure_ascii=False, default=str)
            
def load_settings():
    global CONFIG
    try:
        with open(SETTINGS_DIR, encoding="utf-8") as f: CONFIG = json.load(f)
        if "JSON_DIR" in CONFIG: CONFIG["JSON_DIR"] = Path(CONFIG["JSON_DIR"])
        if "OUTPUT_PATH" in CONFIG: CONFIG["OUTPUT_PATH"] = Path(CONFIG["OUTPUT_PATH"])
    
    except (FileNotFoundError, json.JSONDecodeError):
        print("Settings file is corrupted or does not exist.\nCreating file with default settings...")
        for key, value in CONFIG.items():
            save_setting(key, value)
        
def unsigned_hex(value):
    """Convert a signed 32-bit integer to the 0xXXXXXXXX form used by the game."""
    if not isinstance(value, int) or isinstance(value, bool):
        return value

    if value < 0:
        value += 2 ** 32

    return "0x" + format(value, "08X")


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)

def extract_section(text, section_name, start_marker=None, end_marker=None):
    """
    Extract one MyTags section such as:

        CHARA_PARAM_INFO (
            ParamID|True
            ...
        )

    When start_marker/end_marker are provided, only search inside that
    larger block. This matters because MyTags.txt contains definitions
    for multiple Yokai Watch games.
    """
    if start_marker is not None:
        start = text.find(start_marker)
        if start == -1:
            raise ValueError(f"Could not find MyTags block: {start_marker}")
    else:
        start = 0

    if end_marker is not None:
        end = text.find(end_marker, start)
        if end == -1:
            raise ValueError(f"Could not find MyTags block end: {end_marker}")
        block = text[start:end]
    else:
        block = text[start:]

    pattern = rf"(?m)^\s*{re.escape(section_name)}\s*\(\s*(.*?)^\s*\)"
    match = re.search(pattern, block, re.DOTALL)
    
    #print(f"{pattern}\n{block}\n{start_marker}\n{end_marker}\n")

    if not match:
        raise ValueError(
            f"Could not find '{section_name}' in the selected MyTags block."
        )

    return match.group(1)


def load_schema(tags_path, section_name, game_marker="YW2"):
    """
    Read data from the set `YW{X}` section of MyTags.txt.

    MyTags uses:
        FieldName|True   -> ID/hash field
        FieldName|False  -> ordinary numeric field
    """
    tags_text = tags_path.read_text(encoding="utf-8")
    
    end_marker = MARKER_LIST[NEXT_MARKER[game_marker]]

    game_block = extract_section(
        tags_text,
        section_name,
        start_marker=f"{game_marker} [",
        end_marker=f"{end_marker} [",
    )

    schema = []

    for line in game_block.splitlines():
        line = line.strip()

        if not line or "|" not in line:
            continue

        field_name, id_flag = line.split("|", 1)
        field_name = field_name.strip()
        id_flag = id_flag.strip()

        schema.append({
            "name": field_name,
            "is_id": id_flag.lower() == "true",
        })

    if not schema:
        raise ValueError(f"{section_name} schema in MyTags.txt is empty.")

    return schema


def build_text_map(data):
    """
    Build a lookup for both TEXT_INFO and NOUN_INFO.

    CfgBin export uses:
        TEXT_INFO:
            [ID, Index, String, Variant]

        NOUN_INFO:
            [ID, Entry, ..., String, ..., Value1..Value4]
    """
    text_map = {}

    for item in data:
        name = item.get("Name")

        if name not in {"TEXT_INFO", "NOUN_INFO"}:
            continue

        values = [entry.get("Value") for entry in item.get("Values", [])]

        if not values or not isinstance(values[0], int):
            continue

        text_id = unsigned_hex(values[0])

        if name == "TEXT_INFO":
            text_map[text_id] = {
                "TextID": text_id,
                "TextIndex": values[1] if len(values) > 1 else None,
                "TextString": values[2] if len(values) > 2 else None,
                "TextVariant": values[3] if len(values) > 3 else None,
            }

        else:  # NOUN_INFO
            text_map[text_id] = {
                "TextID": text_id,
                "TextEntry": values[1] if len(values) > 1 else None,
                "TextString": values[5] if len(values) > 5 else None,
                "TextValue1": values[10] if len(values) > 10 else None,
                "TextValue2": values[11] if len(values) > 11 else None,
                "TextValue3": values[12] if len(values) > 12 else None,
                "TextValue4": values[13] if len(values) > 13 else None,
            }

    return text_map

def get_text_string(text_map, text_id):
    if text_id is None:
        return None

    data = text_map.get(text_id)

    if not data:
        return None

    return data.get("TextString")

def build_value_map(values, schema, map_value=False):
    # Build dictionary for values from database entry
    
    mapped = {}

    #print(f"{values}\n{schema}")
    #print(zip(schema,values))
    
    for value, field in zip(values, schema):
        #print(field,value)
        mapped[field["name"]] = (
            unsigned_hex(value)
            if field["is_id"]
            else value
        )
        
    if map_value:
        if not mapped.get(map_value, False): return None, None
        return mapped[map_value], mapped
    return mapped

def incorrect_value_name_exception(values, schema, key_value):
    current_attempt = key_value
    while True:
        user_input = input(f"Can't find {current_attempt} inside the entry.\nChoose another value?\n(Write value name or press enter to interupt iteration)\n").strip()
        if user_input == '': return None, None, key_value
        current_attempt = user_input
        map_id, data_map = build_value_map(values, schema, current_attempt)
        if map_id is not None: return map_id, data_map, current_attempt
            
def iterate_through_json_data(json_data):
    json_map = {}
    json_map_entry = None
    schema_dict = {}
    key_by_value = False
    key_index = 0
    dup = 0 # If we find entry with same name, using this to distinguish them
    entry_len = {"item_name": '', "original": 0, "actual": 0}
    
    for index, item in enumerate(json_data):
        item_name = item.get("Name")
        if ("_END" in item_name or "_LIST_BEG" in item_name or "_BEGIN" in item_name) == False:
            # Load data
                
            values = [entry.get("Value") for entry in item.get("Values", [])]
                
            # Mapping schema to values
            if key_by_value:
                map_id, data_map = build_value_map(values, schema_dict[item_name], key_by_value)
                
                # If user wrote incorrect value name:
                if map_id is None:
                    map_id, data_map, key_by_value = (incorrect_value_name_exception(values, schema_dict[item_name], key_by_value))
                    if map_id is None: return False
                json_map_entry[map_id] = data_map
            else:
                data_map = build_value_map(values, schema_dict[item_name])
                json_map_entry.append(data_map)
            entry_len["actual"]+=1
        else:
            if "_END" in item_name: continue
            item_name = item_name.replace("_BEGIN",'').replace("_LIST_BEG",'')

            if entry_len["original"] != entry_len["actual"]: 
                return print (f"{json_map_entry} length: {entry_len['actual']}\ndoes not match json length: {entry_len['original']}")
            entry_len = {"item_name": item_name, "original": item['Values'][0]['Value'], "actual": 0}
            
            dup=0
            if not schema_dict.get(item_name, False):
                # loading schema if it's encountered for the first time
                data_schema = load_schema(MYTAGS_PATH, item_name, CONFIG["GAME_MARKER"])
                schema_dict[item_name] = data_schema
                '''
                val_len = len(values)
                schm_len = len(data_schema)
                
                print(f"""
                {item_name} schema: {schm_len} fields
                {item_name} records: {val_len}
                """)
                if schm_len != val_len:
                    raise ValueError(
                        f"A {item_name} record does not match the MyTags schema: "
                        f"{val_len} values vs {schm_len} fields."
                    )
                '''
                # cfg.bin files can either be stored as array
                # either as hash maps
                
                next_index = index + 1
                if next_index < len(json_data):
                    next_item = json_data[next_index]
                    values = [entry.get("Value") for entry in next_item.get("Values", [])]
                    data_map = build_value_map(values, schema_dict[item_name])
                else: next_item = None
                if next_item:
                    key_by_value = input(f"{data_map}\nMap {item_name} schema by value?\n(Write value name or press enter to use array instead)\n").strip()
                    if key_by_value == '': key_by_value = False
                
                if key_by_value:
                    json_map[item_name] = {}
                else:
                    json_map[item_name] = []
                json_map_entry = json_map[item_name]
            else:
                dup=1
                while json_map.get(f"{item_name}_{dup}", False): dup+=1
                
                if key_by_value: json_map[f"{item_name}_{dup}"] = {}
                else: json_map[f"{item_name}_{dup}"] = []
                json_map_entry = json_map[f"{item_name}_{dup}"]
    return json_map
            
def main():
    load_settings()    

    while True:
        user_input = int_input(input(f"""
{'='*20}--COMMAND LIST--{'='*20}
1 - Import tags from MyTags.txt to JSON file
2 - Set game title (Current: {CONFIG["GAME_MARKER"]})
3 - Set output directory (Current: {CONFIG["OUTPUT_PATH"]})
4 - Set JSON directory (Current: {CONFIG["JSON_DIR"]})
{'='*56}
Input: """))
        
        match user_input:
            case 1:
                json_file = input(f"JSON File name: ")
                if json_file == '': continue
                DATA_PATH = CONFIG["JSON_DIR"] / json_file
                try: json_data = load_json(DATA_PATH)
                except FileNotFoundError: 
                    print(f"Could not find the file {DATA_PATH}")
                    continue
                json_map = iterate_through_json_data(json_data)
                
                # CONFIG["OUTPUT_PATH"] = DATA_DIR / json_file    
                if json_map:
                    with open(CONFIG["OUTPUT_PATH"] / json_file, "w", encoding="utf-8") as f:
                        json.dump(
                            json_map,
                            f,
                            indent=4,
                            ensure_ascii=False,
                        )

                    print(f"\nSaved: {CONFIG['OUTPUT_PATH'] / json_file}")
                else:
                    print("Could not save JSON File")

            case 2:
                marker_index = int_input(input(f"""
{'='*20}--SELECT TITLE--{'='*20}
1 - YW1
2 - YW2
3 - YW3
4 - YWB
5 - YWB2
6 - YW4
7 - YSH
8 - NNK1
9 - SW
10 - IEGO
{'='*56}
Input: """))
                CONFIG["GAME_MARKER"] = MARKER_LIST[marker_index-1]
                save_setting("GAME_MARKER", CONFIG["GAME_MARKER"])
            case 3: 
                CONFIG["OUTPUT_PATH"] = Path(input(f"New output directory: "))
                save_setting("OUTPUT_PATH", CONFIG["OUTPUT_PATH"])
            case 4: 
                CONFIG["JSON_DIR"] = Path(input(f"New JSON directory: "))
                save_setting("JSON_DIR", CONFIG["JSON_DIR"])
            case _: continue


if __name__ == "__main__": main()