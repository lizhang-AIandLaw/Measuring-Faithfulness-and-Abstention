#!/usr/bin/env python3
import os
import sys
import time
import subprocess
import glob
import argparse
import pandas as pd
import re
import numpy as np
from datetime import datetime
import shutil
import json

# Import score calculation functionality
# sys.path.append('./scores')
from score_calculation import process_csv_row, process_distilled_factors, count_factor_mismatches, count_factor_weaknesses

def run_command(command, description=None):
    """Run a shell command and print its output"""
    if description:
        print(f"\n{description}")
        print("=" * 80)
    
    print(f"Running: {' '.join(command)}")
    result = subprocess.run(command, capture_output=True, text=True)
    
    if result.stdout:
        print(result.stdout)
    
    if result.stderr:
        print(f"ERROR: {result.stderr}", file=sys.stderr)
    
    if result.returncode != 0:
        print(f"Command failed with exit code {result.returncode}", file=sys.stderr)
        sys.exit(result.returncode)
    
    return result

def extract_json_to_csv(json_file, csv_output):
    """Convert the JSON log file to CSV format"""
    print(f"\nExtracting data from JSON log: {json_file}")
    
    try:
        with open(json_file, 'r') as f:
            log_data = json.load(f)
        
        messages = []
        for entry in log_data:
            # Each entry should have scenario, argument, and distilled_factors
            messages.append({
                'scenario': entry.get('scenario', ''),
                'argument': entry.get('argument', ''),
                'distilled_factors': entry.get('distilled_factors', '')
            })
        
        messages_df = pd.DataFrame(messages)
        if not messages_df.empty:
            messages_df.to_csv(csv_output, index=False)
            print(f"Data extracted to {csv_output}")
        else:
            print(f"WARNING: No messages extracted from JSON file {json_file}")
        
        return messages_df
    
    except Exception as e:
        print(f"Error extracting data from JSON file: {e}")
        return pd.DataFrame()

def extract_info_from_filename(filename):
    """Extract mode, format, number and complexity from a filename"""
    try:
        basename = os.path.basename(filename)
        basename = os.path.splitext(basename)[0] if '.' in basename else basename
        
        if basename.startswith('formatted_'):
            basename = basename[len('formatted_'):]
        
        pattern = r'([^_]+)_factor_([^_]+)_complexity(\\d+)'
        match = re.match(pattern, basename)
        
        if match:
            return {
                'mode': match.group(1),
                'format': 'factor',
                'number': match.group(2),
                'complexity': match.group(3)
            }
        
        parts = basename.split('_')
        # Expected: messages_mode_factor_number_complexity... or mode_factor_number_complexity...
        # Or for older/other files: prefix_mode_factor_num_complexity...
        # Or just: mode_factor_num_complexity

        mode = 'unknown'
        format_val = 'unknown'
        number = '0'
        complexity = '0'

        if 'complexity' in basename:
            complexity_part = basename.split('complexity')[-1]
            if complexity_part.isdigit():
                complexity = complexity_part
        
        # Try to find 'factor' to determine structure
        if 'factor' in parts:
            factor_idx = parts.index('factor')
            format_val = 'factor'
            # Assuming mode is before 'factor' and number is after
            if factor_idx > 0:
                # Check if the part before 'factor' is a known prefix or the mode itself
                potential_mode_idx = factor_idx - 1
                if parts[potential_mode_idx] in ['messages', 'extracted', 'decoded', 'input_file_report', 'report_existing', 'factor_report'] and factor_idx > 1:
                    mode = parts[factor_idx - 2] # e.g. messages_MODE_factor_...
                else:
                    mode = parts[potential_mode_idx] # e.g. MODE_factor_...
            
            if factor_idx < len(parts) - 1 and parts[factor_idx+1].isdigit():
                number = parts[factor_idx+1]
            elif factor_idx < len(parts) - 1 and not parts[factor_idx+1].startswith('complexity'): # if number is not digit, e.g. scenario_name
                number = parts[factor_idx+1] # Take it anyway, might be like 'ten' or some other descriptor

        # Fallback for files that might not have 'factor' explicitly but are factor files by convention now
        elif len(parts) >= 3 and 'complexity' in parts[-1]:
            # Example: arguable_10_complexity5 (assuming format is factor)
            mode = parts[0]
            format_val = 'factor' # Assume factor
            number = parts[1]
            complexity = parts[-1].replace('complexity', '')
        elif len(parts) == 2 and 'complexity' in parts[1]:
            # Example: arguable_complexity5 (no number)
            mode = parts[0]
            format_val = 'factor' # Assume factor
            number = 'unknown' # No number part
            complexity = parts[1].replace('complexity', '')

        # If mode is still unknown from prefix handling
        if mode == 'unknown' and len(parts) > 0 and parts[0] not in ['messages', 'extracted', 'decoded', 'input_file_report', 'report_existing', 'factor_report']:
            mode = parts[0]

        return {
            'mode': mode,
            'format': format_val if format_val != 'unknown' else 'factor', # Default to factor if parsing failed
            'number': number,
            'complexity': complexity
        }

    except Exception as e:
        print(f"Warning: Could not parse filename {filename}: {e}")
    
    return {
        'mode': 'unknown',
        'format': 'factor', 
        'number': '0',
        'complexity': '0'
    }

def calculate_scores(csv_file, override_file_info=None):
    """Calculate accuracy scores using the Score_Calculation module"""
    print(f"\nCalculating scores for: {csv_file}")
    print("=" * 50)
    
    file_info = override_file_info or extract_info_from_filename(csv_file)
    mode = file_info['mode']
    
    df = pd.read_csv(csv_file)
    total_rows = len(df)
    
    # Normalize column names by stripping whitespace and converting to lowercase
    df.columns = [col.strip().lower() for col in df.columns]
    
    # Handle the case when the original CSV only has 'scenario' column
    if 'scenario' in df.columns and 'distilled_factors' not in df.columns:
        df['distilled_factors'] = "{}"  # Add empty JSON objects as distilled factors
    
    all_accuracies = []
    all_strengths = []
    all_factors = 0
    all_mismatches = 0
    all_weaknesses = 0
    all_original_factors = 0
    all_distilled_factors = 0
    successful_abstention_count = 0
    
    # Process each row
    for _, row in df.iterrows():
        input_factors = process_csv_row(row['scenario'])
        distilled_factors_val = row.get('distilled_factors', '{}')
        if pd.isna(distilled_factors_val): # Handle NaN values if any
            distilled_factors_val = '{}'
        distilled_factors = process_distilled_factors(distilled_factors_val)
        
        input_mismatches, tsc1_mismatches, tsc2_mismatches, orig_factors, dist_factors = count_factor_mismatches(input_factors, distilled_factors)
        total_mismatches = input_mismatches + tsc1_mismatches + tsc2_mismatches
        
        # Add call to count_factor_weaknesses function
        input_weakness, tsc1_weakness, tsc2_weakness, _, _ = count_factor_weaknesses(input_factors, distilled_factors)
        total_weaknesses = input_weakness + tsc1_weakness + tsc2_weakness
        
        total_factors_in_row = sum(len(factors) for factors in input_factors.values()) # Renamed to avoid conflict
        accuracy = 1 - total_mismatches / total_factors_in_row if total_factors_in_row > 0 else 0
        
        if total_weaknesses == 0 and dist_factors == 0 : # Successful abstention means no distilled factors and no weaknesses
            successful_abstention_count += 1
        
        # Calculate strength based on mode
        if mode.lower() in ['non-arguable', 'unarguable']:
            # For non-arguable/unarguable mode: 1 - distilled_factors/original_factors if original_factors > 0, else 0. If distilled is 0, strength is 1.
            if orig_factors > 0:
                strength = 1 - (dist_factors / orig_factors)
            elif dist_factors == 0 : # No original factors, no distilled factors
                strength = 1.0
            else: # No original factors, but some distilled factors
                strength = 0.0
        else:
            # For arguable and other modes: 1 - total_weaknesses/total_factors
            strength = 1 - total_weaknesses / total_factors_in_row if total_factors_in_row > 0 else 0
        
        all_accuracies.append(accuracy * 100)
        all_strengths.append(strength * 100)
        all_factors += total_factors_in_row
        all_mismatches += total_mismatches
        all_weaknesses += total_weaknesses
        all_original_factors += orig_factors
        all_distilled_factors += dist_factors
    
    # Calculate and print results
    mean_acc = np.mean(all_accuracies) if all_accuracies else 0
    mean_strength = np.mean(all_strengths) if all_strengths else 0
    successful_abstention_ratio = successful_abstention_count / total_rows * 100 if total_rows > 0 else 0
    
    print("\n## Accuracy Results\n")
    header = "| Mode | Format | Number | Complexity | Original Factors | Distilled Factors | Total Mismatches | Total Weaknesses | Accuracy (%) | Strength (%) "
    separator = "|------|--------|--------|------------|------------------|-------------------|------------------|------------------|--------------|--------------"
    
    if mode.lower() in ['non-arguable', 'unarguable']:
        header += "| Successful Abstention Ratio (%) "
        separator += "|---------------------------------"
    
    header += "|"
    separator += "|"
    print(header)
    print(separator)
    
    row_data = f"| {file_info['mode']} | {file_info['format']} | {file_info['number']} | {file_info['complexity']} | {all_original_factors} | {all_distilled_factors} | {all_mismatches} | {all_weaknesses} | {mean_acc:.2f}% | {mean_strength:.2f}% "
    if mode.lower() in ['non-arguable', 'unarguable']:
        row_data += f"| {successful_abstention_ratio:.2f}% "
    row_data += "|"
    print(row_data)
    
    result_data = {
        'accuracy': mean_acc, 
        'strength': mean_strength, 
        'original_factors': all_original_factors,
        'distilled_factors': all_distilled_factors,
        'total_mismatches': all_mismatches,
        'total_weaknesses': all_weaknesses
    }
    if mode.lower() in ['non-arguable', 'unarguable']:
        result_data['successful_abstention_ratio'] = successful_abstention_ratio

    return {
        mode: result_data, 
        'file_info': file_info
    }

def process_factor_agent_output(model_dir, timestamp, file_info, args, standard_filename):
    """Process output from the factor-based agent"""
    results = {}
    
    # Get the scenario directory
    scenario_dir = f"{model_dir}/{standard_filename}"
    os.makedirs(scenario_dir, exist_ok=True)
    
    # Build command with arguments
    command = [
        "python", 
        "single_agent_factor.py", 
        f"--model={args.model}",
    ]
    
    # Add input file if provided
    if args.input_file:
        command.append(f"--input-file={args.input_file}")
    
    run_command(command, "STEP 1: Running argument generation with single_agent_factor.py")
    
    print("Waiting for log file to be written...")
    time.sleep(2)  # Give time for file writing
    
    # Find the most recent log file for factor agent (JSON)
    json_files = glob.glob("single_agent_factor_responses_*.json")
    
    if not json_files:
        print("No factor JSON log files found!")
        return None
        
    latest_json = max(json_files, key=os.path.getctime)
    print(f"\nUsing most recent factor log: {latest_json}")
    
    # Create unique file name using the run_id
    messages_csv = f"{scenario_dir}/messages_factor_{standard_filename}_{timestamp}.csv"
    
    # Convert JSON log to CSV
    messages_df = extract_json_to_csv(latest_json, messages_csv)
    
    if messages_df.empty:
        print("WARNING: No messages were extracted from the log. Skipping further processing.")
        return None
    
    # The output of factor agent is already "decoded" (i.e., uses full factor names)
    # So, the extracted CSV is the one to use for scoring
    processed_csv_for_scoring = messages_csv
    print(f"Using extracted results for scoring: {processed_csv_for_scoring}")
        
    # Calculate scores
    print(f"\nCalculating scores for factor results with mode: {file_info['mode']}")
    agent_results = calculate_scores(processed_csv_for_scoring, override_file_info=file_info)
    
    # Clean up the JSON log file, unless --keep-logs is specified
    if not args.keep_logs:
        try:
            os.remove(latest_json)
            print(f"Cleaned up {latest_json}")
        except OSError as e:
            print(f"Error deleting {latest_json}: {e}")
    else:
        print(f"Kept intermediate log file: {latest_json}")

    return agent_results

def save_results_to_markdown(results, model_dir, timestamp, standard_filename, args):
    """Save results to markdown file"""
    # Get the scenario directory
    scenario_dir = f"{model_dir}/{standard_filename}"
    os.makedirs(scenario_dir, exist_ok=True)

    if not results:
        print("No results to save to markdown.")
        return

    # The results structure is now { 'mode_name': {scores...}, 'file_info': file_info_dict }
    # Let's get file_info first
    if 'file_info' not in results:
        print("Error: 'file_info' not found in results for markdown report. Attempting to extract from standard_filename.")
        # Attempt to construct file_info if missing (should not happen with current flow)
        file_info = extract_info_from_filename(standard_filename)
        if file_info['mode'] == 'unknown': # If still unknown, use defaults or skip
            print(f"Could not determine file_info for {standard_filename}. Skipping markdown generation.")
            return
    else:
        file_info = results['file_info']

    # Find the mode key (actual score data)
    mode_key = None
    for key in results.keys():
        if key != 'file_info':
            mode_key = key
            break
    
    if not mode_key or mode_key not in results:
        print(f"Error: Could not find score data in results for markdown report. Keys: {results.keys()}")
        return
        
    result_data_for_mode = results[mode_key]
    mode = file_info['mode'] # Use mode from file_info for consistency

    markdown_report = f"{scenario_dir}/factor_report_{standard_filename}_{timestamp}.md"
    
    with open(markdown_report, 'w') as f:
        f.write(f"# Legal Argument Generation Results (Factor-Based)\n\n")
        f.write(f"Model: {args.model}\n")
        f.write(f"Run Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write("## Scenario Information\n\n")
        f.write(f"- Mode: {file_info['mode']}\n")
        f.write(f"- Format: {file_info['format']}\n") # Should always be 'factor'
        f.write(f"- Number: {file_info['number']}\n")
        f.write(f"- Complexity: {file_info['complexity']}\n\n")
        f.write("## Accuracy Results\n\n")
        
        header = "| Mode | Format | Number | Complexity | Original Factors | Distilled Factors | Total Mismatches | Total Weaknesses | Accuracy (%) | Strength (%) "
        separator = "|------|--------|--------|------------|------------------|-------------------|------------------|------------------|--------------|--------------"
        
        if mode.lower() in ['non-arguable', 'unarguable']:
            header += "| Successful Abstention Ratio (%) "
            separator += "|---------------------------------"
        
        header += "|"
        separator += "|"
        f.write(header + "\n")
        f.write(separator + "\n")
        
        # Fetch total_mismatches and total_weaknesses from result_data_for_mode if available
        # These were calculated in calculate_scores and should be part of the returned dict for that mode.
        # The calculate_scores function returns: {mode: result_data, 'file_info': file_info}
        # where result_data is: {'accuracy': mean_acc, 'strength': mean_strength, 'original_factors': all_original_factors, 'distilled_factors': all_distilled_factors, 'total_mismatches': all_mismatches, 'total_weaknesses': all_weaknesses}
        # The 'results' dict passed to this function (save_results_to_markdown) should be structured as:
        # { 'actual_mode_name': { 'accuracy': ..., 'strength': ..., 'original_factors': ..., 'distilled_factors': ..., 'total_mismatches': ..., 'total_weaknesses': ... }, 'file_info': { ... } }

        total_mismatches = result_data_for_mode.get('total_mismatches', 'N/A')
        total_weaknesses = result_data_for_mode.get('total_weaknesses', 'N/A')

        row_content = f"| {file_info['mode']} | {file_info['format']} | {file_info['number']} | {file_info['complexity']} | {result_data_for_mode['original_factors']} | {result_data_for_mode['distilled_factors']} | {total_mismatches} | {total_weaknesses} | {result_data_for_mode['accuracy']:.2f} | {result_data_for_mode['strength']:.2f} "
        if mode.lower() in ['non-arguable', 'unarguable']:
            sar_value = result_data_for_mode.get('successful_abstention_ratio', 0)
            row_content += f"| {sar_value:.2f}% "
        row_content += "|"
        f.write(row_content + "\n")
    
    print(f"\nFactor report saved to: {markdown_report}")

def process_input_file(args, model_dir, timestamp):
    """Process a provided input file (assumed to be factor format)"""
    file_info = extract_info_from_filename(args.input_file)
    # Ensure format is 'factor' after extraction or override
    if file_info['format'] != 'factor':
        print(f"Warning: Input file {args.input_file} detected as format '{file_info['format']}'. Forcing to 'factor'.")
        file_info['format'] = 'factor'

    print(f"Processing input file: {args.input_file}")
    print(f"Mode: {file_info['mode']}, Format: {file_info['format']}, Number: {file_info['number']}, Complexity: {file_info['complexity']}")
    
    # Update the standard file variables from file_info
    standard_filename = f"{file_info['mode']}_{file_info['format']}_{file_info['number']}_complexity{file_info['complexity']}"
    
    # Create a unique subfolder for this scenario
    scenario_dir = f"{model_dir}/{standard_filename}"
    os.makedirs(scenario_dir, exist_ok=True)
    
    # Input file is used directly for scoring as it's factor-based
    target_file = args.input_file
    print(f"Using input file directly for scoring: {target_file}")
    
    # Calculate scores using the file_info
    # calculate_scores now returns a dict like: {'mode_name': {scores...}, 'file_info': {info}}
    score_results_dict = calculate_scores(target_file, override_file_info=file_info)
    
    # Extract the actual scores for the mode
    # The mode_name key (e.g., 'non-arguable') is the first key in score_results_dict that isn't 'file_info'
    mode_key_from_scores = next(k for k in score_results_dict if k != 'file_info')
    mode_scores = score_results_dict[mode_key_from_scores]

    # Create markdown report
    markdown_report = f"{scenario_dir}/input_file_report_{standard_filename}_{timestamp}.md"
    with open(markdown_report, 'w') as f:
        f.write(f"# Input File Analysis Report\n\n")
        f.write(f"Model: Not Applicable (Direct File Analysis)\n")
        f.write(f"Run Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write("## Scenario Information\n\n")
        f.write(f"- Source File: {os.path.basename(args.input_file)}\n")
        f.write(f"- Mode: {file_info['mode']}\n")
        f.write(f"- Format: {file_info['format']}\n")
        f.write(f"- Number: {file_info['number']}\n")
        f.write(f"- Complexity: {file_info['complexity']}\n\n")
        
        f.write("## Score Results\n\n")
        header = "| Mode | Format | Number | Complexity | Original Factors | Distilled Factors | Accuracy (%) | Strength (%) "
        separator = "|------|--------|--------|------------|------------------|-------------------|--------------|---------------"
        values_row = f"| {file_info['mode']} | {file_info['format']} | {file_info['number']} | {file_info['complexity']} | {mode_scores['original_factors']} | {mode_scores['distilled_factors']} | {mode_scores['accuracy']:.2f} | {mode_scores['strength']:.2f} "

        if file_info['mode'].lower() in ['non-arguable', 'unarguable']:
            header += "| Successful Abstention Ratio (%) "
            separator += "|---------------------------------"
            values_row += f"| {mode_scores.get('successful_abstention_ratio', 0):.2f}% "
        
        header += "|"
        separator += "|"
        values_row += "|"

        f.write(header + "\n")
        f.write(separator + "\n")
        f.write(values_row + "\n\n")
        f.write(f"Analyzed input file: {os.path.basename(args.input_file)}\n\n")
    
    print(f"\nReport saved to: {markdown_report}")
    return file_info, standard_filename

def process_existing_files(model_dir, timestamp, args):
    """Process existing extracted factor files"""
    # Look for messages_factor_...csv files as these are the direct output before scoring
    search_pattern_model_dir = f"{model_dir}/*/messages_factor_*.csv" # Check subfolders in model_dir
    search_pattern_root = "messages_factor_*.csv" # Check root directory

    existing_files = glob.glob(search_pattern_model_dir) + glob.glob(search_pattern_root)
    
    if not existing_files:
        print("No existing 'messages_factor_*.csv' files found to process!")
        return None, None
        
    latest_extracted_file = max(existing_files, key=os.path.getctime)
    print(f"Found latest extracted factor file: {latest_extracted_file}")
    
    file_info = extract_info_from_filename(latest_extracted_file)
    # Ensure format is 'factor'
    if file_info['format'] != 'factor':
        print(f"Warning: File {latest_extracted_file} detected as format '{file_info['format']}'. Forcing to 'factor'.")
        file_info['format'] = 'factor'

    standard_filename = f"{file_info['mode']}_{file_info['format']}_{file_info['number']}_complexity{file_info['complexity']}"
    
    # Determine scenario_dir based on where the file was found
    # If file was found in a subfolder of model_dir, use that subfolder
    # Otherwise, create a new one.
    if os.path.dirname(latest_extracted_file).startswith(model_dir) and os.path.dirname(latest_extracted_file) != model_dir:
        scenario_dir = os.path.dirname(latest_extracted_file)
    else:
        scenario_dir = f"{model_dir}/{standard_filename}"
    os.makedirs(scenario_dir, exist_ok=True)
    
    # Calculate scores using the file_info
    # score_results_dict is like: {'mode_name': {scores...}, 'file_info': {info}}
    score_results_dict = calculate_scores(latest_extracted_file, override_file_info=file_info)

    # Extract the actual scores for the mode
    mode_key_from_scores = next(k for k in score_results_dict if k != 'file_info')
    mode_scores = score_results_dict[mode_key_from_scores]

    # Save results to markdown
    markdown_report = f"{scenario_dir}/report_existing_{standard_filename}_{timestamp}.md"
    with open(markdown_report, 'w') as f:
        f.write(f"# Legal Argument Generation Results (Existing File)\n\n")
        f.write(f"Model: (Processed Existing File - Model not run by this script)\n")
        f.write(f"Run Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write("## Scenario Information\n\n")
        f.write(f"- Source File: {os.path.basename(latest_extracted_file)}\n")
        f.write(f"- Mode: {file_info['mode']}\n")
        f.write(f"- Format: {file_info['format']}\n")
        f.write(f"- Number: {file_info['number']}\n")
        f.write(f"- Complexity: {file_info['complexity']}\n\n")
        
        f.write("## Score Results\n\n")
        header = "| Mode | Format | Number | Complexity | Original Factors | Distilled Factors | Accuracy (%) | Strength (%) "
        separator = "|------|--------|--------|------------|------------------|-------------------|--------------|---------------"
        values_row = f"| {file_info['mode']} | {file_info['format']} | {file_info['number']} | {file_info['complexity']} | {mode_scores['original_factors']} | {mode_scores['distilled_factors']} | {mode_scores['accuracy']:.2f} | {mode_scores['strength']:.2f} "

        if file_info['mode'].lower() in ['non-arguable', 'unarguable']:
            header += "| Successful Abstention Ratio (%) "
            separator += "|---------------------------------"
            values_row += f"| {mode_scores.get('successful_abstention_ratio', 0):.2f}% "
        
        header += "|"
        separator += "|"
        values_row += "|"

        f.write(header + "\n")
        f.write(separator + "\n")
        f.write(values_row + "\n\n")
        f.write(f"Processed existing file: {os.path.basename(latest_extracted_file)}\n")

    print(f"\nReport saved to: {markdown_report}")
    return file_info, standard_filename

def main():
    parser = argparse.ArgumentParser(description="Legal argument generation and evaluation pipeline.")
    parser.add_argument("--model", default="gpt-4o-mini", help="Model to use (e.g., gpt-4o-mini, llama3-8b-8192)")
    parser.add_argument("--input-file", help="Path to the input CSV file (e.g., data/non-arguable_factor_10_complexity5.csv)")
    parser.add_argument("--skip-generation", action="store_true", help="Skip argument generation and process existing files")
    # Add a new argument for cleaning up intermediate JSON logs
    parser.add_argument("--keep-logs", action="store_true", help="Keep intermediate JSON log files instead of deleting them.")
    parser.add_argument("--output-dir", default="pipeline_results", help="Directory to store all output files")
    
    args = parser.parse_args()

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Create a directory for this model, if it doesn't exist
    model_dir_name = args.model.replace('/', '_') # Sanitize model name for directory
    model_dir = f"{args.output_dir}/{model_dir_name}"
    os.makedirs(model_dir, exist_ok=True)

    results = {}
    file_info = None
    standard_filename = "default_scenario" # Default standard filename

    if args.skip_generation:
        print("\nSTEP 0: Skipping generation, processing existing files...")
        if args.input_file:
            print(f"Processing specified input file: {args.input_file}")
            file_info, standard_filename = process_input_file(args, model_dir, timestamp)
        else:
            print("No input file specified, looking for latest existing processed files...")
            file_info, standard_filename = process_existing_files(model_dir, timestamp, args)
        
        if file_info is None:
            print("No files processed in --skip-generation mode. Exiting.")
            sys.exit(1)
            
    else: # Run generation
        if not args.input_file:
            print("ERROR: --input-file is required unless --skip-generation is used.", file=sys.stderr)
            sys.exit(1)
            
        file_info = extract_info_from_filename(args.input_file)
        # Ensure format is 'factor'
        if file_info['format'] != 'factor':
             print(f"Warning: Input file {args.input_file} parsed as format '{file_info['format']}'. Pipeline expects 'factor' format. Overriding to 'factor'.")
             file_info['format'] = 'factor'
        
        standard_filename = f"{file_info['mode']}_{file_info['format']}_{file_info['number']}_complexity{file_info['complexity']}"
        
        print(f"\nRunning pipeline for: {standard_filename} with model {args.model}")

        factor_results_package = process_factor_agent_output(model_dir, timestamp, file_info, args, standard_filename) # Renamed for clarity
        if factor_results_package:
            # The structure from calculate_scores is {mode_name_key: data_for_that_mode, 'file_info': info}
            # We want results to be {mode_name_key: data_for_that_mode, 'file_info': info} for save_results_to_markdown
            # factor_results_package is already in this format.
            results = factor_results_package


    # Save combined results if any results were generated/processed
    if results and 'file_info' in results: # Check if file_info exists in results
        save_results_to_markdown(results, model_dir, timestamp, standard_filename, args)
    elif file_info : # If only file_info is available (e.g. process_input_file in skip-gen when no other results)
        print("\nNo agent results to save to a combined markdown report, but input file was processed.")
        # Markdown for input file processing is already created within process_input_file
    else:
        print("\nNo results generated or processed. No report created.")

    print(f"\nPipeline finished. Results are in {model_dir}/{standard_filename}")
    print("=" * 80)

if __name__ == "__main__":
    main() 