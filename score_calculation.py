import os
import pandas as pd
import re
import numpy as np
from scipy import stats

def extract_case_factors(input_text: str) -> tuple[list[str], list[str], list[str]]:
    """Extract factors from Input Scenario and both TSC cases.
    
    Args:
        input_text: Raw text containing Input Scenario and TSC cases
        
    Returns:
        Tuple of (input_factors, tsc1_factors, tsc2_factors) lists
    """
    # Initialize lists to store factors
    input_factors = []
    tsc1_factors = []
    tsc2_factors = []
    
    # Define regex patterns
    input_pattern = re.compile(r'Input\s+Scenario')
    tsc1_pattern = re.compile(r'TSC\s+1')
    tsc2_pattern = re.compile(r'TSC\s+2')
    factor_pattern = re.compile(r'F\d+\s+[^(]+\([PD]\)')
    
    current_section = None
    
    # Process each line
    for line in input_text.split('\n'):
        line = line.strip()
        if not line:
            continue
            
        if re.search(input_pattern, line):
            current_section = 'input'
        elif re.search(tsc1_pattern, line):
            current_section = 'tsc1'
        elif re.search(tsc2_pattern, line):
            current_section = 'tsc2'
        elif re.search(factor_pattern, line):
            factor = line.strip().rstrip(',')
            if current_section == 'input':
                input_factors.append(factor)
            elif current_section == 'tsc1':
                tsc1_factors.append(factor)
            elif current_section == 'tsc2':
                tsc2_factors.append(factor)
                
    return input_factors, tsc1_factors, tsc2_factors

def process_csv_row(row_text: str) -> dict[str, list[str]]:
    """Process a single CSV row and extract all factors.
    
    Args:
        row_text: Raw text from CSV cell containing cases
        
    Returns:
        Dictionary with input, TSC1 and TSC2 factors
    """
    input_factors, tsc1_factors, tsc2_factors = extract_case_factors(row_text)
    
    return {
        'Input': input_factors,
        'TSC1': tsc1_factors, 
        'TSC2': tsc2_factors
    }

def process_distilled_factors(row_text: str) -> dict:
    """Process distilled factors text and return structured factor data.
    
    Args:
        row_text: Raw text from CSV cell containing distilled factors in JSON-like format
        
    Returns:
        Dictionary containing the structured factor data matching the input format
    """
    # First, remove content before "</think>" and "</think>" itself
    think_end = row_text.find("</think>")
    if think_end != -1:
        row_text = row_text[think_end + len("</think>"):].strip()
    
    # Extract the JSON-like content by removing any leading/trailing text
    json_content = re.search(r'\{.*\}', row_text, re.DOTALL)
    if not json_content:
        return {
            "Input Case": {},
            "TSC1": {},
            "TSC2": {}
        }
        
    # Extract the JSON text
    json_text = json_content.group(0)
    
    # Use regex to extract the case factors
    input_case_match = re.search(r'"Input Case"\s*:\s*{(.*?)}', json_text, re.DOTALL)
    tsc1_match = re.search(r'"TSC1"\s*:\s*{(.*?)}', json_text, re.DOTALL)
    tsc2_match = re.search(r'"TSC2"\s*:\s*{(.*?)}', json_text, re.DOTALL)
    
    result = {
        "Input Case": {},
        "TSC1": {},
        "TSC2": {}
    }
    
    # Process Input Case factors
    if input_case_match:
        factors_text = input_case_match.group(1)
        factors = re.findall(r'"([^"]+)"', factors_text)
        result["Input Case"] = {factor: None for factor in factors}
    
    # Process TSC1 factors
    if tsc1_match:
        factors_text = tsc1_match.group(1)
        factors = re.findall(r'"([^"]+)"', factors_text)
        result["TSC1"] = {factor: None for factor in factors}
    
    # Process TSC2 factors
    if tsc2_match:
        factors_text = tsc2_match.group(1)
        factors = re.findall(r'"([^"]+)"', factors_text)
        result["TSC2"] = {factor: None for factor in factors}
    
    return result

def count_factor_mismatches(input_factors: dict[str, list[str]], 
                          distilled_factors: dict) -> tuple[int, int, int, int, int]:
    """Count factors claimed as common but not present in both cases.
    
    Args:
        input_factors: Dictionary containing factors from input text
        distilled_factors: Dictionary containing the structured factor data
        
    Returns:
        Tuple of (input_mismatch_count, tsc1_mismatch_count, tsc2_mismatch_count, 
                 original_total_factor_count, distilled_total_factor_count)
    """
    input_mismatch = 0
    tsc1_mismatch = 0
    tsc2_mismatch = 0
    
    # Extract factor names from the distilled factors
    distilled_input_factors = list(distilled_factors["Input Case"].keys())
    distilled_tsc1_factors = list(distilled_factors["TSC1"].keys())
    distilled_tsc2_factors = list(distilled_factors["TSC2"].keys())
    
    # Calculate total factors in original and distilled input
    original_total_factors = len(input_factors['Input']) + len(input_factors['TSC1']) + len(input_factors['TSC2'])
    distilled_total_factors = len(distilled_input_factors) + len(distilled_tsc1_factors) + len(distilled_tsc2_factors)
    
    # Check for factors claimed in distilled Input but not in actual Input
    for factor in distilled_input_factors:
        if factor not in input_factors['Input']:
            input_mismatch += 1
    
    # Check for factors claimed in distilled TSC1 but not in actual TSC1
    for factor in distilled_tsc1_factors:
        if factor not in input_factors['TSC1']:
            tsc1_mismatch += 1
    
    # Check for factors claimed in distilled TSC2 but not in actual TSC2
    for factor in distilled_tsc2_factors:
        if factor not in input_factors['TSC2']:
            tsc2_mismatch += 1
            
    return input_mismatch, tsc1_mismatch, tsc2_mismatch, original_total_factors, distilled_total_factors

def count_factor_weaknesses(input_factors: dict[str, list[str]], 
                          distilled_factors: dict) -> tuple[int, int, int, int, int]:
    """Count factors present in actual cases but not claimed in distilled factors.
    
    Args:
        input_factors: Dictionary containing factors from input text
        distilled_factors: Dictionary containing the structured factor data
        
    Returns:
        Tuple of (input_weakness_count, tsc1_weakness_count, tsc2_weakness_count,
                 original_total_factor_count, distilled_total_factor_count)
    """
    input_weakness = 0
    tsc1_weakness = 0
    tsc2_weakness = 0
    
    # Extract factor names from the distilled factors
    distilled_input_factors = list(distilled_factors["Input Case"].keys())
    distilled_tsc1_factors = list(distilled_factors["TSC1"].keys())
    distilled_tsc2_factors = list(distilled_factors["TSC2"].keys())
    
    # Calculate total factors in original and distilled input
    original_total_factors = len(input_factors['Input']) + len(input_factors['TSC1']) + len(input_factors['TSC2'])
    distilled_total_factors = len(distilled_input_factors) + len(distilled_tsc1_factors) + len(distilled_tsc2_factors)
    
    # Check for factors in actual Input but not claimed in distilled Input
    for factor in input_factors['Input']:
        if factor not in distilled_input_factors:
            input_weakness += 1

    # Check for factors in actual TSC1 but not claimed in distilled TSC1
    for factor in input_factors['TSC1']:
        if factor not in distilled_tsc1_factors:
            tsc1_weakness += 1
    
    # Check for factors in actual TSC2 but not claimed in distilled TSC2
    for factor in input_factors['TSC2']:
        if factor not in distilled_tsc2_factors:
            tsc2_weakness += 1
            
    return input_weakness, tsc1_weakness, tsc2_weakness, original_total_factors, distilled_total_factors

def process_csv_file(file_path: str) -> None:
    """Process a single CSV file and print its statistics."""
    print(f"\nProcessing file: {file_path}")
    print("=" * 50)
    
    df = pd.read_csv(file_path)
    total_rows = len(df)
    
    # Lists to store accuracy values and total factors
    all_accuracies = []
    all_strengths = []
    all_factors = 0
    all_mismatches = 0
    all_weaknesses = 0
    all_original_factors = 0
    all_distilled_factors = 0
    successful_abstention_count = 0
    
    # Process each row
    for index, row in df.iterrows():
        # Process the input factors from the first column
        input_factors = process_csv_row(row.iloc[0])
        
        # Process the distilled factors from the third column using the new format
        distilled_factors = process_distilled_factors(row.iloc[2])
        
        # Calculate mismatches
        input_mismatch, tsc1_mismatch, tsc2_mismatch, orig_factors, dist_factors = count_factor_mismatches(input_factors, distilled_factors)
        total_mismatches = input_mismatch + tsc1_mismatch + tsc2_mismatch
        
        # Calculate weaknesses
        input_weakness, tsc1_weakness, tsc2_weakness, _, _ = count_factor_weaknesses(input_factors, distilled_factors)
        total_weaknesses = input_weakness + tsc1_weakness + tsc2_weakness
        
        total_factors = sum(len(factors) for factors in input_factors.values())
        
        # Check if all categories in distilled_factors are empty
        if not distilled_factors.get("Input Case") and \
           not distilled_factors.get("TSC1") and \
           not distilled_factors.get("TSC2"):
            successful_abstention_count += 1
            
        # Calculate accuracy and strength for the current row FIRST
        accuracy = 1 - total_mismatches / orig_factors if orig_factors > 0 else 0
        strength = 1 - total_weaknesses / orig_factors if orig_factors > 0 else 0
        
        all_accuracies.append(accuracy * 100)
        all_strengths.append(strength * 100)
        all_factors += total_factors
        all_mismatches += total_mismatches
        all_weaknesses += total_weaknesses
        all_original_factors += orig_factors
        all_distilled_factors += dist_factors
        
    # Calculate and print overall results
    mean_acc = np.mean(all_accuracies) if all_accuracies else 0
    mean_strength = np.mean(all_strengths) if all_strengths else 0
    successful_abstention_ratio = successful_abstention_count / total_rows if total_rows > 0 else 0
    
    print(f"\nOverall statistics:")
    print(f"Total rows: {total_rows}")
    print(f"Successful abstention count: {successful_abstention_count}")
    print(f"Total factors: {all_factors}")
    print(f"Total original factors: {all_original_factors}")
    print(f"Total distilled factors: {all_distilled_factors}")
    print(f"Total mismatches: {all_mismatches}")
    print(f"Total weaknesses: {all_weaknesses}")
    print(f"Accuracy: {mean_acc:.2f}%")
    print(f"Strength: {mean_strength:.2f}%")
    print(f"Successful Abstention Ratio: {successful_abstention_ratio * 100:.2f}%")
    
    return all_factors, all_original_factors, all_distilled_factors, all_mismatches, all_weaknesses, mean_acc, mean_strength, successful_abstention_ratio

def main():
    # Get all CSV files in current directory
    csv_files = [f for f in os.listdir('.') if f.endswith('.csv')]
    
    if not csv_files:
        print("No CSV files found in current directory!")
        return
        
    # Process each CSV file
    for csv_file in csv_files:
        process_csv_file(csv_file)

if __name__ == "__main__":
    main()