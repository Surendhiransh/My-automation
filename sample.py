import pandas as pd
import re
import ast
import math 
from typing import List, Tuple, Set

# DYNAMIC SPECIAL PROCESSORS LIST
SPECIAL_PROCESSORS = [
    'Intel Celeron',
    'Intel Pentium',
    'AMD Sempron',
    'AMD Athlon'
]

def is_special_processor(s: str) -> bool:
    """
    Check if the string contains any special processor from the dynamic list.
    """
    for processor in SPECIAL_PROCESSORS:
        if processor.lower() in s.lower():
            return True
    return False

def parse_entry(s: str) -> Tuple[List[str], str]:
    """
    Dynamic parser for a single entry string.
    Extracts and expands processors, extracts chipset.
    Handles various processor/chipset formats.
    """
    
    # 🌟 FIX 1: Ensure input is a valid non-NaN string
    if pd.isna(s) or (isinstance(s, float) and math.isnan(s)):
        return [], '' 

    s = str(s) # Explicitly convert to string for safety

    original_s = s.strip("' ").replace('\n', ' ')
    s = original_s

    # **CLEAN HTML ENTITIES LIKE &#8203 (zero-width space)**
    s = re.sub(r'&#\d+;?', '', s)
    
    # Clean (N/A), (F), incomplete fragments, and normalize spaces
    s = re.sub(r'\s*\(N/A\)\s*|\s*\(N\s*|\s*A\)\s*|\s*\(F\)\s*|\(\s*\)', '', s)
    s = re.sub(r'\s+', ' ', s).strip()

    # Handle malformed chipsets like '#8203 (Bolton-D2H)'
    s = re.sub(r'#\d+\s*(\([A-Za-z0-9-]+\))', r'\1', s)

    processors: List[str] = []
    chipset = ''
    proc_str = s
    socket = ''

    # 1. PRIORITY HANDLING: AMD A-Series APU pattern 
    amd_apu_pattern = re.compile(
        r'^(AMD\s+A-Series\s+APU)\s*'  
        r'(\(FM\d+\+?\))\s*'           
        r'([A-Z0-9-]+[KkTt]?)\s*'     
        r'(AMD\s+[A-Z0-9]+)\s*'       
        r'(\([A-Za-z0-9-]+\))$',     
        re.IGNORECASE
    )
    amd_match = amd_apu_pattern.search(original_s)
    if amd_match:
        proc_base = amd_match.group(1).strip()
        socket_str = amd_match.group(2).strip()
        proc_model = amd_match.group(3).strip()
        chipset_base = amd_match.group(4).strip()
        chipset_variant = amd_match.group(5).strip()

        processors = [f"{proc_base} {socket_str} {proc_model}".strip()] 
        chipset = f"{chipset_base} {chipset_variant}".strip()
        
        return processors, chipset


    # 2. Extract Socket (if present)
    socket_match = re.search(r'\((FM\d+\+?|AM\d+\+?)\)', s)
    if socket_match:
        socket = socket_match.group(1)
        s = re.sub(r'\s*\((FM\d+\+?|AM\d+\+?)\)\s*', ' ', s).strip()


    # 3. GENERIC CHIPSET EXTRACTION 
    
    # 🌟 NEW LOGIC: Look for [Processor] [Vendor] [Chipset] pattern (e.g., Intel Pentium B940 Intel HM65)
    vendor_pattern = r'\s(Intel|AMD|Nvidia)\s'
    vendor_match_iterator = re.finditer(vendor_pattern, s, re.IGNORECASE)
    
    vendor_match = None
    for i, match in enumerate(vendor_match_iterator):
        if i == 1:
            vendor_match = match
            break
    
    if vendor_match:
        chipset = s[vendor_match.start() + 1:].strip() 
        proc_str = s[:vendor_match.start()].strip()    
    else:
        # Continue with existing chipset patterns 
        chipset_patterns = [
            r'(Intel|AMD|Nvidia)\s+[A-Za-z0-9-]+(?:\s*\([A-Za-z0-9-]+\))?\s*(Chipset|SoC|Series)?$', 
            r'(Nvidia)\s+(GeForce|nForce)\s+\d+[a-zA-Z]?\s*(Series)?$',
            r'\(([A-Za-z0-9-]{2,})\)$', 
        ]

        chipset_match = None
        for pattern in chipset_patterns:
            # Handle variant bracket match separately
            if pattern == r'\(([A-Za-z0-9-]{2,})\)$':
                match = re.search(pattern, s, re.IGNORECASE)
                if match:
                    proc_str = s[:match.start()].strip()
                    vendor_match = re.search(r'(Intel|AMD|Nvidia)\s+([A-Z0-9]+)\s*$', proc_str, re.IGNORECASE)
                    
                    if vendor_match:
                        chipset = f"{vendor_match.group(1)} {vendor_match.group(2)} ({match.group(1)})"
                        proc_str = proc_str[:vendor_match.start()].strip()
                    else:
                        chipset = f"AMD ({match.group(1)})" 
                        
                    break
            
            # For standard chipset patterns
            chipset_match = re.search(pattern, s, re.IGNORECASE)
            if chipset_match:
                chipset = chipset_match.group(0).strip()
                proc_str = s[:chipset_match.start()].strip()
                break
        else:
            proc_str = s 


    # 4. PROCESSOR SEPARATION (Now that chipset is removed from proc_str)
    prefix_match = re.match(r'^(Intel|AMD|Nvidia)\s+([A-Za-z0-9]+(?:\s+[A-Za-z0-9]+)*)\s*', proc_str, re.IGNORECASE)
    if prefix_match:
        base_prefix = f"{prefix_match.group(1)} {prefix_match.group(2)}".strip()
        proc_str = proc_str[len(base_prefix):].strip()
    else:
        base_prefix = ''
        proc_str = proc_str.strip()

    # Simplified handling for non-expanded single processor
    processors = [f"{base_prefix} {proc_str}".strip()]

    # Add socket back to processors if present and not already in the name
    if socket and not any(f'({socket})' in p for p in processors):
        processors = [f"{p} ({socket})" for p in processors]

    # Filter valid processors and clean up spaces
    processors = [p for p in processors if len(p.strip()) > 8 and not p.endswith('(')]
    processors = [re.sub(r'\s+', ' ', p).strip() for p in processors]

    # 🌟 CHANGE: Removed the line `if is_special_processor(original_s): chipset = ''` 
    # This ensures that chipsets like 'Intel HM65' are NOT discarded just because the processor is a 'Special Processor'.
        
    return processors, chipset

# Process each row
def process_row(proc_list_str: str) -> Tuple[str, str]:
    
    # Handle NaN/Missing values immediately 
    if pd.isna(proc_list_str) or (isinstance(proc_list_str, float) and math.isnan(proc_list_str)):
        return '[]', '[]'

    proc_list_str = str(proc_list_str) 

    try:
        proc_list = ast.literal_eval(proc_list_str)
        if not isinstance(proc_list, list):
            proc_list = [proc_list]
    except (ValueError, SyntaxError):
        proc_list = [proc_list_str]

    all_processors: List[str] = []
    chipsets: Set[str] = set() 

    for entry in proc_list:
        if pd.isna(entry): 
            continue 
            
        entry = str(entry) 

        procs, chip = parse_entry(entry)
        all_processors.extend(procs)
        if chip:
            chipsets.add(chip.strip())

    # Format processors as stringified list, sorted and unique
    processors_joined = f"[{', '.join(f'{p!r}' for p in sorted(set(all_processors)))}]" if all_processors else '[]'

    # Format chipset as stringified list, sorted and unique
    chipset_joined = f"[{', '.join(f'{c!r}' for c in sorted(chipsets))}]" if chipsets else '[]'

    return processors_joined, chipset_joined

# --- MAIN EXECUTION ---

# Read input CSV
input_file = 'Kingston_DB_import_chunk_1.csv'
try:
    df = pd.read_csv(input_file)
except FileNotFoundError:
    print(f"Error: The input file '{input_file}' was not found. Using the requested dynamic test data.")
    # Dummy DataFrame using your specific input
    df = pd.DataFrame({
        'processor': [
            "['Intel Pentium B940 Intel HM65']", # Your test case (Should work now)
            "['Intel Core i5 10500(T)', 'Intel Core i7 10700']", # Case with no chipset info
            "['AMD A-Series APU (FM2+) A8-7600 AMD A88X (Bolton-D4)']", 
        ]
    })
    
# Apply to DataFrame
df[['processor', 'chipset']] = df['processor'].apply(process_row).apply(pd.Series)

# Save output
output_file = 'output.csv'
df.to_csv(output_file, index=False)

print(f"Output saved to {output_file}")