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
        if map_value in mapped:
            return mapped[map_value], mapped

        # Tolerate repr-escaped input like 'SteffID?\\Num' where the
        # real key is 'SteffID?\Num'. Only applies if collapsing the
        # doubled backslashes actually hits a real field.
        unescaped = map_value.replace("\\\\", "\\")
        if unescaped != map_value and unescaped in mapped:
            return mapped[unescaped], mapped

        return None, None
    return mapped

def incorrect_value_name_exception(values, schema, key_value):
    current_attempt = key_value
    while True:
        user_input = input(f"Can't find {current_attempt} inside the entry.\nChoose another value?\n(Write value name or press enter to interupt iteration)\n").strip()
        if user_input == '': return None, None, key_value
        current_attempt = user_input
        map_id, data_map = build_value_map(values, schema, current_attempt)
        if map_id is not None: return map_id, data_map, current_attempt
        
def configure_key_by_value(item_name, data_map):
    """Choose a field to use as the key for a named hash map.

    Returns the selected field name, or None when the user wants a list.
    """
    field_dump = "\n".join(
        f"    {name} = {value!r}"
        for name, value in data_map.items()
    )

    while True:
        key_by_value = input(f"""
Preview of first {item_name} entry:
{field_dump}

Use one of these fields as the dictionary key?
(Write a field name, e.g. MapName, or press Enter to use an array)
Input: """).strip()

        if not key_by_value:
            return None

        if key_by_value not in data_map:
            print(f"'{key_by_value}' is not a field in {item_name}. Try again.")
            continue

        if data_map[key_by_value] is None:
            print(f"'{key_by_value}' is empty in the preview entry. Choose another field.")
            continue

        return key_by_value


def iterate_through_json_data(json_data):
    json_map = {}
    json_map_entry = None
    schema_dict = {}
    key_fields = {}
    active_key_field = None
    entry_len = {"item_name": "", "original": 0, "actual": 0}

    for index, item in enumerate(json_data):
        item_name = item.get("Name")
        if not item_name:
            continue

        is_end_marker = item_name.endswith("_END")
        is_begin_marker = (
            item_name.endswith("_BEGIN")
            or item_name.endswith("_LIST_BEG")
        )

        if not is_end_marker and not is_begin_marker:
            # Load data from an ordinary entry.
            values = [entry.get("Value") for entry in item.get("Values", [])]

            if item_name not in schema_dict:
                schema_dict[item_name] = load_schema(
                    MYTAGS_PATH, item_name, CONFIG["GAME_MARKER"]
                )

            data_schema = schema_dict[item_name]

            if active_key_field:
                map_id, data_map = build_value_map(
                    values, data_schema, active_key_field
                )

                # If the selected field is missing in this entry, let the
                # user select a replacement field instead of crashing.
                if map_id is None:
                    map_id, data_map, active_key_field = incorrect_value_name_exception(
                        values, data_schema, active_key_field
                    )
                    if map_id is None:
                        return False

                if map_id in json_map_entry:
                    return print(
                        f"Duplicate key {map_id!r} in {entry_len['item_name']}. "
                        f"Choose a field whose values are unique."
                    )

                json_map_entry[map_id] = data_map
            else:
                data_map = build_value_map(values, data_schema)
                json_map_entry.append(data_map)

            entry_len["actual"] += 1
            continue

        # Before moving to the next block (or closing the current block),
        # make sure its declared ChildCount matches the number of records.
        if entry_len["original"] != entry_len["actual"]:
            print(
                f"{entry_len['item_name']} length: {entry_len['actual']}\n"
                f"does not match json length: {entry_len['original']}"
            )
            return None

        if is_end_marker:
            continue

        # Start a new block.
        original_count = 0
        marker_values = item.get("Values", [])
        if marker_values:
            original_count = marker_values[0].get("Value", 0)

        entry_len = {
            "item_name": item_name,
            "original": original_count,
            "actual": 0,
        }

        if item_name not in key_fields:
            # Load the marker schema the first time this block appears.
            marker_schema = load_schema(
                MYTAGS_PATH, item_name, CONFIG["GAME_MARKER"]
            )
            schema_dict[item_name] = marker_schema
            active_key_field = None

            # Most list-like blocks contain only ChildCount. The actual
            # record schema is the name of the next ordinary entry.
            if (
                len(marker_schema) == 1
                and marker_schema[0]["name"] == "ChildCount"
            ):
                next_item = next(
                    (
                        candidate
                        for candidate in json_data[index + 1:]
                        if candidate.get("Name")
                        and not candidate["Name"].endswith("_END")
                        and not candidate["Name"].endswith("_BEGIN")
                        and not candidate["Name"].endswith("_LIST_BEG")
                    ),
                    None,
                )

                if next_item is not None:
                    next_item_name = next_item["Name"]
                    data_schema = load_schema(
                        MYTAGS_PATH, next_item_name, CONFIG["GAME_MARKER"]
                    )
                    schema_dict[next_item_name] = data_schema

                    values = [
                        entry.get("Value")
                        for entry in next_item.get("Values", [])
                    ]
                    preview_map = build_value_map(values, data_schema)
                    active_key_field = configure_key_by_value(
                        next_item_name, preview_map
                    )

            key_fields[item_name] = active_key_field
        else:
            # Repeated blocks reuse the key field selected for this marker.
            active_key_field = key_fields[item_name]

        # Keep repeated blocks separate, as the original script intended.
        output_name = item_name
        duplicate_index = 1
        while output_name in json_map:
            output_name = f"{item_name}_{duplicate_index}"
            duplicate_index += 1

        json_map[output_name] = {} if active_key_field else []
        json_map_entry = json_map[output_name]

    # Also validate the final block in files that omit a closing marker.
    if entry_len["original"] != entry_len["actual"]:
        print(
            f"{entry_len['item_name']} length: {entry_len['actual']}\n"
            f"does not match json length: {entry_len['original']}"
        )
        return None

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
                    output_file = CONFIG["OUTPUT_PATH"] / json_file
                    output_file.parent.mkdir(parents=True, exist_ok=True)
                    with open(output_file, "w", encoding="utf-8") as f:
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