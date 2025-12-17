import pandas as pd
import re
import ast
import math
from typing import List, Tuple, Set, Union, Optional

class ProcessorParser:
    """
    Dynamically configurable class for parsing processor and chipset information
    from strings, handling various complex formats and cleaning requirements.
    """

    # Pattern for processor + chipset separated by + sign (for cases like 'Intel i7 + Nvidia GeForce')
    _PLUS_SEPARATOR_PATTERN = re.compile(
        r'^([^+]+?)\s*\+\s*([^+]+)$',
        re.IGNORECASE
    )
    
    # Pattern to handle processor string with chipset in brackets (for cases like 'VIA Nano X2 U4025 (dual-core) (N/A)')
    _PROCESSOR_CHIPSET_PATTERN = re.compile(
        r'^(?P<processor>[A-Za-z0-9\s\(\)-]+(?:\s*\([^\)]*\))*)\s*(\((?P<chipset>[A-Za-z0-9\s\(\)-]+)\))?$',
        re.IGNORECASE
    )

    def __init__(self, special_processors: Optional[List[str]] = None):
        """
        Initializes the parser with a dynamic list of special processors.
        The list is used to prevent simple processor names from being incorrectly identified as chipsets.
        """
        if special_processors is None:
            # Default list containing your specified processors
            self.SPECIAL_PROCESSORS = [
                'Intel Celeron',
                'Intel Pentium',
                'AMD Sempron',
                'AMD Athlon',
                'VIA Nano'
            ]
        else:
            self.SPECIAL_PROCESSORS = [p.lower() for p in special_processors]

    def _is_special_processor(self, s: str) -> bool:
        """
        Check if the string contains any special processor from the dynamic list.
        """
        s_lower = s.lower().strip()
        for processor in self.SPECIAL_PROCESSORS:
            if s_lower == processor.lower():
                return True
        return False

    def parse_entry(self, s: Union[str, float]) -> Tuple[List[str], str]:
        """
        Dynamic parser for a single entry string to extract processor and chipset information.

        Sample Input:
        - "Intel i7 + Nvidia GeForce"
        - "VIA Nano X2 U4025 (dual-core) (N/A)"
        - "Intel i3"

        Sample Output:
        - (['Intel i7'], 'Nvidia GeForce')
        - (['VIA Nano X2 U4025 (dual-core)'], '(N/A)')
        - (['Intel i3'], '')
        """
        
        if pd.isna(s) or (isinstance(s, float) and math.isnan(s)):
            return [], ''

        s = str(s).strip()

        # Handling plus sign separator cases (like 'Intel i7 + Nvidia GeForce')
        plus_match = self._PLUS_SEPARATOR_PATTERN.search(s)
        if plus_match:
            processor = plus_match.group(1).strip()
            chipset = plus_match.group(2).strip()
            return [processor], chipset

        # Handling generic processor-chipset with optional bracket for chipset
        chipset_match = self._PROCESSOR_CHIPSET_PATTERN.search(s)
        if chipset_match:
            processor = chipset_match.group('processor').strip()
            chipset = chipset_match.group('chipset') if chipset_match.group('chipset') else ''
            return [processor], chipset

        # If no matching pattern, just return the original string as processor, with empty chipset
        return [s], ''

    def _process_row(self, proc_list_str: Union[str, float]) -> Tuple[str, str]:
        """
        Process a row from the CSV to extract processor and chipset information.

        Sample Input:
        - "['Intel i7 + Nvidia GeForce', 'VIA Nano X2 U4025 (dual-core) (N/A)']"
        - "Intel i5"
        
        Sample Output:
        - ("['Intel i7']", "['Nvidia GeForce']")
        - ("['Intel i5']", '[]')
        """
        
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
            procs, chip = self.parse_entry(entry)
            all_processors.extend(procs)
            if chip:
                chipsets.add(chip.strip())

        processors_joined = f"[{', '.join(f'{p!r}' for p in sorted(set(all_processors)))}]" if all_processors else '[]'
        chipset_joined = f"[{', '.join(f'{c!r}' for c in sorted(chipsets))}]" if chipsets else '[]'

        return processors_joined, chipset_joined

    def process_dataframe(self, df: pd.DataFrame, column_name: str = 'processor') -> pd.DataFrame:
        """
        Process a DataFrame to extract processor and chipset info.

        Sample Input:
        - DataFrame with a column 'processor' containing processor data like 'Intel i7 + Nvidia GeForce', 'VIA Nano X2 U4025 (dual-core) (N/A)'
        
        Sample Output:
        - DataFrame with two additional columns: 'processor' and 'chipset'
        """
        df[[column_name, 'chipset']] = df[column_name].apply(self._process_row).apply(pd.Series)
        return df

    def process_csv(self, input_file: str, output_file: str, column_name: str = 'processor'):
        """
        Process a CSV file to extract and save the processor and chipset data.

        Sample Input:
        - Input CSV file with a 'processor' column containing processor info
        - Example: 'Intel i7 + Nvidia GeForce', 'Intel i3', 'VIA Nano X2 U4025 (dual-core) (N/A)'

        Sample Output:
        - Output CSV with 'processor' and 'chipset' columns extracted and cleaned.
        """
        try:
            df = pd.read_csv(input_file)
            print(f"✅ Successfully read input file: '{input_file}'")
        except FileNotFoundError:
            print(f"❌ Error: The input file '{input_file}' was not found. Please ensure the file exists.")
            return

        df_processed = self.process_dataframe(df, column_name=column_name)
        
        df_processed.to_csv(output_file, index=False)
        print(f"🎉 Processing complete. Output saved to '{output_file}'")


# --- MAIN EXECUTION (IMPLEMENTATION) ---

if __name__ == '__main__':
    
    # 1. Define Execution Parameters based on user request
    DYNAMIC_INPUT_FILE = 'Kingston_DB_import_chunk_4.csv'  # Path to input CSV file
    DYNAMIC_OUTPUT_FILE = 'chunk_4.csv'  # Path to save output CSV file
    PROCESS_COLUMN = 'processor'  # Column name in the CSV containing processor data

    # 2. Instantiate the Dynamic Parser (Using the default list which includes all specified processors)
    parser = ProcessorParser()

    print("\n--- 💻 Starting Processor and Chipset Parsing ---")
    print(f"Input File: {DYNAMIC_INPUT_FILE}")
    print(f"Output File: {DYNAMIC_OUTPUT_FILE}")
    print(f"Column to Process: '{PROCESS_COLUMN}'")

    # 3. Execute the CSV processing function
    parser.process_csv(
        input_file=DYNAMIC_INPUT_FILE,
        output_file=DYNAMIC_OUTPUT_FILE,
        column_name=PROCESS_COLUMN
    )

    print("\n--- ✅ Process Finished ---")
