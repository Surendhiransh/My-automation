import pandas as pd
import re
import ast
from typing import List, Tuple, Set
import glob
import os

# ========== COMPILED REGEX PATTERNS ==========
# Compile once at module level for performance
AMD_APU_PATTERN = re.compile(
    r'^(AMD\s+A-Series\s+APU)\s*'  
    r'(\(FM\d+\+?\))\s*'           
    r'([A-Z0-9-]+[KkTt]?)\s*'     
    r'(AMD\s+[A-Z0-9]+)\s*'       
    r'(\([A-Za-z0-9-]+\))$',     
    re.IGNORECASE
)

SOCKET_PATTERN = re.compile(r'\((FM\d+\+?|AM\d+\+?)\)')

VENDOR_PATTERN = re.compile(r'\s(Intel|AMD|Nvidia)\s', re.IGNORECASE)

VENDOR_PREFIX_PATTERN = re.compile(
    r'^(Intel|AMD|Nvidia)\s+([A-Za-z0-9]+(?:\s+[A-Za-z0-9]+)*)\s*',
    re.IGNORECASE
)

CHIPSET_PATTERNS = [
    re.compile(r'(Intel|AMD|Nvidia)\s+[A-Za-z0-9-]+(?:\s*\([A-Za-z0-9-]+\))?\s*(Chipset|SoC|Series)?$', re.IGNORECASE),
    re.compile(r'(Nvidia)\s+(GeForce|nForce)\s+\d+[a-zA-Z]?\s*(Series)?$', re.IGNORECASE),
    re.compile(r'\(([A-Za-z0-9-]{2,})\)$', re.IGNORECASE),
]

HTML_ENTITY_PATTERN = re.compile(r'&#\d+;?')
CLEANUP_PATTERN = re.compile(r'\s*\(N/A\)\s*|\s*\(N\s*|\s*A\)\s*|\s*\(F\)\s*|\(\s*\)')
MALFORMED_CHIPSET_PATTERN = re.compile(r'#\d+\s*(\([A-Za-z0-9-]+\))')
WHITESPACE_PATTERN = re.compile(r'\s+')


def _is_nan(value) -> bool:
    """Check if value is NaN or missing."""
    if pd.isna(value):
        return True
    return False


def parse_entry(s: str) -> Tuple[List[str], str]:
    """
    Dynamic parser for a single entry string.
    Extracts and expands processors, extracts chipset.
    Handles various processor/chipset formats.
    """
    
    # Handle NaN/missing values
    if _is_nan(s):
        return [], ''

    s = str(s)
    original_s = s.strip("' ").replace('\n', ' ')
    s = original_s

    # Clean HTML entities
    s = HTML_ENTITY_PATTERN.sub('', s)
    
    # Clean (N/A), (F), incomplete fragments, and normalize spaces
    s = CLEANUP_PATTERN.sub('', s)
    s = WHITESPACE_PATTERN.sub(' ', s).strip()

    # Handle malformed chipsets
    s = MALFORMED_CHIPSET_PATTERN.sub(r'\1', s)

    processors: List[str] = []
    chipset = ''
    proc_str = s
    socket = ''

    # 1. PRIORITY HANDLING: AMD A-Series APU pattern 
    amd_match = AMD_APU_PATTERN.search(original_s)
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
    socket_match = SOCKET_PATTERN.search(s)
    if socket_match:
        socket = socket_match.group(1)
        s = SOCKET_PATTERN.sub(' ', s).strip()

    # 3. GENERIC CHIPSET EXTRACTION 
    vendor_match = None
    for i, match in enumerate(VENDOR_PATTERN.finditer(s)):
        if i == 1:
            vendor_match = match
            break
    
    if vendor_match:
        chipset = s[vendor_match.start() + 1:].strip() 
        proc_str = s[:vendor_match.start()].strip()    
    else:
        # Try chipset patterns
        chipset_match = None
        for pattern in CHIPSET_PATTERNS:
            match = pattern.search(s, re.IGNORECASE)
            if match:
                if pattern == CHIPSET_PATTERNS[2]:  # Bracket pattern
                    proc_str = s[:match.start()].strip()
                    vendor_match = re.search(r'(Intel|AMD|Nvidia)\s+([A-Z0-9]+)\s*$', proc_str, re.IGNORECASE)
                    
                    if vendor_match:
                        chipset = f"{vendor_match.group(1)} {vendor_match.group(2)} ({match.group(1)})"
                        proc_str = proc_str[:vendor_match.start()].strip()
                    else:
                        chipset = f"AMD ({match.group(1)})"
                else:
                    chipset = match.group(0).strip()
                    proc_str = s[:match.start()].strip()
                
                break
        else:
            proc_str = s 

    # 4. PROCESSOR SEPARATION
    prefix_match = VENDOR_PREFIX_PATTERN.match(proc_str)
    if prefix_match:
        base_prefix = f"{prefix_match.group(1)} {prefix_match.group(2)}".strip()
        proc_str = proc_str[len(base_prefix):].strip()
    else:
        base_prefix = ''
        proc_str = proc_str.strip()

    processors = [f"{base_prefix} {proc_str}".strip()]

    # Add socket back to processors if present
    if socket and not any(f'({socket})' in p for p in processors):
        processors = [f"{p} ({socket})" for p in processors]

    # Filter valid processors
    processors = [p for p in processors if len(p.strip()) > 8 and not p.endswith('(')]
    processors = [WHITESPACE_PATTERN.sub(' ', p).strip() for p in processors]
        
    return processors, chipset


def process_row(proc_list_str: str) -> Tuple[str, str]:
    """Process a row and extract processors and chipsets."""
    
    if _is_nan(proc_list_str):
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
        if _is_nan(entry): 
            continue 
            
        entry = str(entry) 

        procs, chip = parse_entry(entry)
        all_processors.extend(procs)
        if chip:
            chipsets.add(chip.strip())

    # Format as stringified lists
    processors_joined = f"[{', '.join(f'{p!r}' for p in sorted(set(all_processors)))}]" if all_processors else '[]'
    chipset_joined = f"[{', '.join(f'{c!r}' for c in sorted(chipsets))}]" if chipsets else '[]'

    return processors_joined, chipset_joined


def process_all_csv_chunks(directory: str = '.', output_file: str = 'output.csv') -> None:
    """
    Process all Kingston DB import CSV chunks dynamically.
    Combines results from all chunks into a single output file.
    """
    
    # Find all Kingston DB import chunk files
    chunk_pattern = os.path.join(directory, 'Kingston_DB_import_chunk_*.csv')
    chunk_files = sorted(glob.glob(chunk_pattern))
    
    if not chunk_files:
        print(f"No chunk files found matching pattern: {chunk_pattern}")
        return
    
    all_dfs = []
    
    for chunk_file in chunk_files:
        print(f"Processing: {chunk_file}")
        try:
            df = pd.read_csv(chunk_file)
            
            # Apply processing
            if 'processor' in df.columns:
                df[['processor', 'chipset']] = df['processor'].apply(process_row).apply(pd.Series)
            
            all_dfs.append(df)
        except Exception as e:
            print(f"Error processing {chunk_file}: {e}")
            continue
    
    if all_dfs:
        # Combine all dataframes
        combined_df = pd.concat(all_dfs, ignore_index=True)
        
        # Save output
        combined_df.to_csv(output_file, index=False)
        print(f"\nOutput saved to {output_file}")
        print(f"Total rows processed: {len(combined_df)}")
    else:
        print("No data to process")


# --- MAIN EXECUTION ---
if __name__ == '__main__':
    # Process all CSV chunks in current directory
    process_all_csv_chunks()
